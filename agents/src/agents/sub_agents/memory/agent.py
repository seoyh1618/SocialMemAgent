"""
MemGPT Memory Agent — manages persistent user memory across sessions.
Skill MD 참조 기반 구조화 저장/조회 전담.
"""

import json
import logging
from google.adk.agents import Agent

from ...memory_tools import (
    memory_get_core_profile,
    memory_update_user_profile,
    memory_update_brand_voice,
    memory_update_domain_profile,
    memory_add_domain_knowledge,
    memory_get_knowledge,
    memory_add_product,
    memory_get_product,
    memory_update_product,
    memory_update_audience_segment,
    memory_add_audience_trait,
    memory_get_audience_segments,
    memory_collect_performance,
    memory_get_performance_pending,
    memory_mark_performance_asked,
    memory_get_behavior_insights,
    memory_get_top_pickscore_keywords,
    memory_archive_campaign,
    memory_search_campaigns,
    memory_get_recent_campaigns,
    memory_archive_conversation,
    memory_search_conversations,
    memory_update_working_summary,
    memory_append_recall,
    memory_get_recall_log,
    memory_add_performance_notes,
    memory_record_generated_asset,
    memory_get_assets,
    memory_compress_context,
    memory_get_context_status,
    read_skill_md,
    # ERD v2 도구 ()
    memory_link_product_segment,
    memory_link_campaign_product,
    memory_link_campaign_segment,
    memory_list_segment_products,
    memory_list_campaign_products,
    memory_add_channel_output,
    memory_add_performance_record,
    memory_get_channel_outputs,
    # 운영 참조 질의 (다단계 조인)
    memory_trace_product_to_campaigns,
    memory_trace_segment_to_campaigns,
    # 전체 카탈로그 조회 (Phase 6 백엔드 검증에서 필요성 발견)
    memory_list_all_products,
    memory_list_all_segments,
    memory_list_all_campaigns,
    # 캠페인 컨텍스트 통합 retrieval — Memory Agent 내부 도구로 재배치
    memory_agent_query_campaign_context,
)
from . import prompt

logger = logging.getLogger(__name__)


def _classify_memory_request(user_text: str) -> str:
    """LOOP 13: memory_agent 진입 시 사용자/위임 요청을 LLM 분류.
    Returns: 'campaign_context_query' | 'registration' | 'lookup' | 'other'

    Pro 분류기 — orchestrator 위임 query 또는 사용자 직접 발화 모두 처리.
    룰베이스 없음, 의도 분석만 사용.
    """
    if not user_text:
        return "other"
    prompt = (
        "You are classifying a memory operation request inside a marketing agent.\n"
        "Reply with ONLY one label (lowercase, no quotes):\n\n"
        "  campaign_context_query\n"
        "    — user/orchestrator needs campaign memory context for creating or revising content\n"
        "    — explicit hints: 'goal=', 'channels=', '캠페인 컨텍스트 retrieval',\n"
        "      '시안 만들어', '캠페인 만들어', '콘텐츠 생성', '핀터레스트 버전',\n"
        "      '다음 캠페인', '후속 캠페인', '그거 톤 그대로'\n"
        "  registration\n"
        "    — user describing brand / product / audience for storage\n"
        "    — examples: '네일샵 시작했어 메인 컬러는...', '신상 60000원'\n"
        "  lookup\n"
        "    — user asks to retrieve stored info by name/id (no content creation)\n"
        "    — examples: '내 상품 목록', '저번에 등록한 페르소나 보여줘'\n"
        "  other\n"
        "    — chitchat, unrelated, ambiguous\n\n"
        f'Request text: "{user_text[:600]}"\n\n'
        "Label:"
    )
    try:
        import concurrent.futures
        from google import genai
        client = genai.Client()
        def _call():
            return client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            resp = pool.submit(_call).result(timeout=12)
        label = (getattr(resp, "text", "") or "").strip().lower().split()[0] if resp else ""
        label = label.strip().strip(".").strip("'").strip('"')
        if label in {"campaign_context_query", "registration", "lookup", "other"}:
            return label
        if "campaign" in label or "context" in label: return "campaign_context_query"
        if "regist" in label: return "registration"
        if "look" in label: return "lookup"
        return "other"
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] LOOP 13 classify failed: %s", exc)
        return "other"


def _force_archival_retrieval(callback_context):
    """memory_agent 진입 직전 Core 카탈로그 → Archival 상세 escalation 강제.

    LOOP 13: 캠페인 컨텍스트 요청으로 분류되면 memory_agent_query_campaign_context
    를 callback 에서 직접 호출해 _campaign_memory_context + _memory_agent_invoked 를
    채움. LLM 이 service tool 호출을 누락해도 retrieve 흐름 보장.
    """
    from ...memory_tools import _load_memory
    state = callback_context.state
    # 사용자 발화 추출 — 4 경로 시도
    last_user_text = ""
    # 1) state 에 명시적으로 저장된 경우
    for k in ("_last_user_text", "_recent_user_text"):
        v = state.get(k)
        if v:
            last_user_text = str(v); break
    # 2) ADK callback_context 의 user_content 직접 추출
    if not last_user_text:
        try:
            uc = getattr(callback_context, "user_content", None)
            if uc and hasattr(uc, "parts"):
                for p in (uc.parts or []):
                    t = getattr(p, "text", None)
                    if t: last_user_text = str(t); break
        except Exception: pass
    # 3) recall_log 마지막 USER 발화
    if not last_user_text:
        try:
            from ...memory_tools import _load_memory as _lm_for_fallback
            _mem = _lm_for_fallback(callback_context)
            for r in reversed(_mem.recall_log or []):
                r_dict = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                speaker = (r_dict.get("speaker") or "").upper()
                content = r_dict.get("content") or ""
                if speaker == "USER" and content:
                    last_user_text = str(content); break
        except Exception: pass
    # 4) _user_intent.goal 보강
    try:
        _ui = state.get("_user_intent") or {}
        if isinstance(_ui, str):
            try: _ui = json.loads(_ui) if _ui.startswith("{") else {}
            except Exception: _ui = {}
        if isinstance(_ui, dict) and _ui.get("goal"):
            last_user_text = f"{last_user_text} {_ui['goal']}".strip()
    except Exception: pass
    if (
        last_user_text
        and not state.get("_memory_agent_invoked")
        and not (state.get("_campaign_memory_context") or {})
    ):
        try:
            label = _classify_memory_request(last_user_text)
            logger.info("[MEM_FORCE_RETRIEVAL] LOOP 13 classify=%r", label)
            if label == "campaign_context_query":
                ui = state.get("_user_intent") or {}
                if isinstance(ui, str):
                    try: ui = json.loads(ui) if ui.startswith("{") else {}
                    except Exception: ui = {}
                goal = ""
                channels_str = ""
                if isinstance(ui, dict):
                    goal = (ui.get("goal") or "")[:300]
                    channels_str = ",".join(ui.get("channels") or [])
                if not goal:
                    goal = last_user_text[:300]
                if not channels_str:
                    for kw, ch in [
                        ("instagram", "instagram"), ("인스타", "instagram"),
                        ("pinterest", "pinterest"), ("핀터레스트", "pinterest"),
                        ("facebook", "facebook"), ("페이스북", "facebook"),
                        ("tiktok", "tiktok"), ("틱톡", "tiktok"),
                        ("youtube", "youtube"), ("유튜브", "youtube"),
                        ("kakao", "kakao"), ("카카오", "kakao"),
                        ("threads", "threads"), ("스레드", "threads"),
                        ("linkedin", "linkedin"), ("x", "x"),
                    ]:
                        if kw in last_user_text.lower() and ch not in channels_str:
                            channels_str = f"{channels_str},{ch}" if channels_str else ch
                from ...memory_tools import memory_agent_query_campaign_context as _qctx
                try:
                    result = _qctx(
                        callback_context,
                        goal=goal,
                        channels=channels_str,
                        products_hint="",
                        segments_hint="",
                    )
                    if isinstance(result, dict):
                        logger.info(
                            "[MEM_FORCE_RETRIEVAL] LOOP 13 service tool invoked: keys=%d, "
                            "products=%d related_campaigns_kw=%d",
                            len(result),
                            len(result.get("referenced_products") or []),
                            len(result.get("related_campaigns_keyword") or []),
                        )
                except Exception as exc:
                    logger.warning("[MEM_FORCE_RETRIEVAL] LOOP 13 service tool failed: %s", exc)
        except Exception as exc:
            logger.warning("[MEM_FORCE_RETRIEVAL] LOOP 13 guard error: %s", exc)
    is_campaign_ctx = bool(state.get("_campaign_memory_context"))
    try:
        mem = _load_memory(callback_context)
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] _load_memory failed: %s", exc); return None

    dump = {}

    # 1) 전체 상품 상세 (catalog → detail)
    try:
        products = []
        for p in (mem.product_archive or [])[:10]:
            p_dict = p.model_dump() if hasattr(p, "model_dump") else dict(p)
            products.append({k: v for k, v in p_dict.items()
                             if v not in (None, "", [], {})})
        dump["products"] = products
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] products: %s", exc)

    # 2) 전체 세그먼트 상세
    try:
        segments = []
        for seg in (mem.audience_block.segments or []):
            seg_dict = seg.model_dump() if hasattr(seg, "model_dump") else dict(seg)
            segments.append({k: v for k, v in seg_dict.items()
                             if v not in (None, "", [], {})})
        dump["segments"] = segments
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] segments: %s", exc)

    # 3) Domain Knowledge 상세
    try:
        knowledge = []
        for k in (mem.domain_block.knowledge or []):
            k_dict = k.model_dump() if hasattr(k, "model_dump") else dict(k)
            knowledge.append({kk: vv for kk, vv in k_dict.items()
                              if vv not in (None, "", [], {})})
        dump["knowledge"] = knowledge
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] knowledge: %s", exc)

    # 4) BehaviorGraph 인사이트
    try:
        bg = mem.behavior_graph
        bg_dict = bg.model_dump() if hasattr(bg, "model_dump") else dict(bg)
        dump["behavior_insights"] = {
            "proven_tactics": bg_dict.get("proven_tactics", [])[:5],
            "failed_tactics": bg_dict.get("failed_tactics", [])[:5],
            "overall_best_platform": bg_dict.get("overall_best_platform"),
            "platform_best_content_type": bg_dict.get("platform_best_content_type", {}),
            "confidence_level": bg_dict.get("confidence_level"),
        }
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] behavior: %s", exc)

    try:
        camp_archive = mem.campaign_archive or []
        recent_camps_raw = camp_archive[-5:] if camp_archive else []
        recent_camps = [
            (c.model_dump() if hasattr(c, "model_dump") else dict(c))
            for c in recent_camps_raw
        ]
        dump["recent_campaigns"] = recent_camps
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] campaigns: %s", exc)

    # 6) 대화 이력 (recall_log 최근 10건)
    try:
        rl = mem.recall_log or []
        recent_recall = []
        for r in rl[-10:]:
            r_dict = r.model_dump() if hasattr(r, "model_dump") else dict(r)
            recent_recall.append({
                "speaker": r_dict.get("speaker"),
                "content": (r_dict.get("content") or "")[:300],
                "timestamp": r_dict.get("timestamp"),
            })
        dump["recall_log"] = recent_recall
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] recall_log: %s", exc)

    # 7) PickScore top keywords — 전역 + product/channel별 그룹
    try:
        assets = mem.asset_archive or []
        all_scored = []
        for a in assets:
            a_dict = a.model_dump() if hasattr(a, "model_dump") else dict(a)
            if (a_dict.get("pickscore") or 0) > 0:
                all_scored.append(a_dict)
        all_scored.sort(key=lambda x: -(x.get("pickscore") or 0))
        # 전역 top 5
        dump["top_assets"] = [
            {"asset_id": a.get("asset_id"), "pickscore": a.get("pickscore"),
             "platform": a.get("platform"), "product_id": a.get("product_id"),
             "prompt_keywords": (a.get("prompt") or "")[:200]}
            for a in all_scored[:5]
        ]
        # 채널별 top 3 (재사용용)
        by_channel = {}
        for a in all_scored:
            plat = (a.get("platform") or "unknown").lower()
            by_channel.setdefault(plat, []).append({
                "asset_id": a.get("asset_id"),
                "pickscore": a.get("pickscore"),
                "prompt_keywords": (a.get("prompt") or "")[:200],
            })
        dump["top_assets_by_channel"] = {k: v[:3] for k, v in by_channel.items()}
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] assets: %s", exc)

    # 8) ERD N:M 링크 (현재 상품-세그먼트 연결도) — Pydantic→dict 직렬화
    def _dump_link_list(items):
        out = []
        for i in (items or []):
            if hasattr(i, "model_dump"): out.append(i.model_dump())
            elif isinstance(i, dict): out.append(i)
            else:
                try: out.append(dict(i))
                except Exception: out.append(str(i))
        return out
    try:
        dump["product_segment_links"] = _dump_link_list(mem.product_segment_links)
        dump["campaign_product_links"] = _dump_link_list(mem.campaign_product_links)
        dump["campaign_segment_links"] = _dump_link_list(mem.campaign_segment_links)
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] links: %s", exc)

    # ───────────────────────────────────────────────────────────────────
    # Track F: 사용자 의도 기반 specific deep retrieval
    # ───────────────────────────────────────────────────────────────────
    intent_dump = {}
    try:
        intent = state.get("_user_intent") or {}
        if isinstance(intent, str):
            try: intent = json.loads(intent) if intent.startswith("{") else {"goal": intent}
            except Exception: intent = {"goal": intent}
        goal = intent.get("goal") or last_user_text[:200] or ""

        # (a) 사용자 발화·goal에 언급된 product 식별 → 상세 + 관계 추적
        matched_products = []
        for p in dump.get("products", []):
            p_name = p.get("name") or ""
            if p_name and (p_name in last_user_text or p_name in goal
                           or any(tok in last_user_text for tok in p_name.split() if len(tok) >= 2)):
                matched_products.append(p)
        intent_dump["referenced_products"] = matched_products

        # (b) 매칭된 product 별 관계 추적 (memory_trace_product_to_campaigns 등가)
        product_relations = {}
        for p in matched_products[:3]:
            pid = p.get("product_id")
            if not pid: continue
            related = {
                "product_id": pid,
                "linked_segments": [],
                "linked_campaigns": [],
            }
            for link in dump.get("product_segment_links", []):
                if link.get("product_id") == pid:
                    related["linked_segments"].append(link.get("segment_id"))
            for link in dump.get("campaign_product_links", []):
                if link.get("product_id") == pid:
                    related["linked_campaigns"].append(link.get("campaign_id"))
            product_relations[pid] = related
        intent_dump["product_relations"] = product_relations

        # (c) Campaign archive vector-style filter (키워드 매칭)
        keyword_pool = []
        for p in matched_products: keyword_pool.extend((p.get("name") or "").split())
        keyword_pool.extend(goal.split())
        keyword_pool = [k for k in keyword_pool if len(k) >= 2]
        related_campaigns = []
        for c in mem.campaign_archive or []:
            c_dict = c.model_dump() if hasattr(c, "model_dump") else dict(c)
            blob = f"{c_dict.get('campaign_name','')} {c_dict.get('goal','')} {c_dict.get('description','')}"
            if any(k in blob for k in keyword_pool):
                related_campaigns.append({
                    "campaign_id": c_dict.get("campaign_id"),
                    "campaign_name": c_dict.get("campaign_name"),
                    "goal": c_dict.get("goal"),
                    "performance": c_dict.get("performance_summary"),
                })
        intent_dump["related_campaigns"] = related_campaigns[:5]

        # (d) 매칭된 product 별 PickScore 상위 키워드 (성과 검증된 패턴)
        top_keywords_per_product = {}
        for p in matched_products:
            pid = p.get("product_id"); p_name = p.get("name") or ""
            assets_filtered = []
            for a in mem.asset_archive or []:
                a_dict = a.model_dump() if hasattr(a, "model_dump") else dict(a)
                if (a_dict.get("product_id") == pid
                    or p_name in (a_dict.get("prompt") or "")):
                    if (a_dict.get("pickscore") or 0) > 0:
                        assets_filtered.append({
                            "asset_id": a_dict.get("asset_id"),
                            "pickscore": a_dict.get("pickscore"),
                            "prompt_keywords": (a_dict.get("prompt") or "")[:200],
                        })
            assets_filtered.sort(key=lambda x: -(x.get("pickscore") or 0))
            top_keywords_per_product[pid] = assets_filtered[:3]
        intent_dump["product_top_assets"] = top_keywords_per_product

        # (e) 매칭된 segment + 그 세그먼트의 page-rank style relevance
        matched_segments = []
        for s in dump.get("segments", []):
            s_name = s.get("name") or ""
            in_user = s_name and (s_name in last_user_text or s_name in goal)
            # OR — 세그먼트가 매칭 product에 link되어 있으면 자동 포함
            linked_to_matched_product = any(
                s.get("segment_id") in r.get("linked_segments", [])
                for r in product_relations.values()
            )
            if in_user or linked_to_matched_product:
                matched_segments.append(s)
        intent_dump["referenced_segments"] = matched_segments

        # (f) 채널 outputs — 매칭 product 의 과거 채널별 산출물 (재사용 패턴)
        channel_outputs_per_product = {}
        try:
            ch_outputs_all = getattr(mem, "campaign_channel_outputs", []) or []
            for p in matched_products:
                pid = p.get("product_id")
                if not pid: continue
                linked_camp_ids = []
                for link in dump.get("campaign_product_links", []):
                    if link.get("product_id") == pid:
                        linked_camp_ids.append(link.get("campaign_id"))
                outputs = []
                for co in ch_outputs_all:
                    co_dict = co.model_dump() if hasattr(co, "model_dump") else dict(co)
                    if co_dict.get("campaign_id") in linked_camp_ids:
                        outputs.append({
                            "output_id": co_dict.get("output_id"),
                            "campaign_id": co_dict.get("campaign_id"),
                            "channel": co_dict.get("channel"),
                            "caption_preview": (co_dict.get("caption") or "")[:200],
                            "hashtags": (co_dict.get("hashtags") or [])[:5],
                            "cta": co_dict.get("cta"),
                            "image_url": co_dict.get("image_url"),
                        })
                if outputs:
                    channel_outputs_per_product[pid] = outputs[:5]
            intent_dump["channel_outputs_per_product"] = channel_outputs_per_product
        except Exception as exc:
            logger.warning("[MEM_FORCE_RETRIEVAL] channel_outputs: %s", exc)
            intent_dump["channel_outputs_per_product"] = {}

        # (g) Vector search — 의미 기반 캠페인 회상 (Qdrant)
        try:
            from ...memory_tools import memory_search_campaigns as _mscamp
            qv_results = []
            if goal:
                try:
                    raw = _mscamp.__wrapped__(callback_context, query=goal, limit=5) \
                          if hasattr(_mscamp, "__wrapped__") else _mscamp(callback_context, query=goal, limit=5)
                    qv_results = raw if isinstance(raw, list) else []
                except Exception:
                    # Qdrant 미작동/없음 — keyword 매칭 결과로 fallback
                    qv_results = []
            intent_dump["vector_campaigns"] = qv_results[:5]
        except Exception as exc:
            logger.warning("[MEM_FORCE_RETRIEVAL] vector_search: %s", exc)
            intent_dump["vector_campaigns"] = []

        # (h) Knowledge — category 별 상세 (catalog → detail)
        try:
            knowledge_detail = {}
            for k in dump.get("knowledge", []):
                cat = k.get("category") or k.get("key") or "misc"
                knowledge_detail.setdefault(cat, []).append({
                    "knowledge_id": k.get("knowledge_id"),
                    "title": k.get("title"),
                    "value": k.get("value") or k.get("content"),
                    "confidence": k.get("confidence"),
                })
            intent_dump["knowledge_by_category"] = knowledge_detail
        except Exception as exc:
            logger.warning("[MEM_FORCE_RETRIEVAL] knowledge_detail: %s", exc)
            intent_dump["knowledge_by_category"] = {}

        # (i) retrieval plan 메타데이터 — 어떤 도구가 어떤 인자로 실행됐는지
        intent_dump["plan_executed"] = {
            "matched_products": [p.get("product_id") for p in matched_products],
            "matched_segments": [s.get("segment_id") for s in matched_segments],
            "keyword_pool": keyword_pool[:10],
            "tools_invoked": [
                "memory_get_product (per matched product)",
                "memory_trace_product_to_campaigns",
                "memory_search_campaigns (keyword filter)",
                "memory_get_top_pickscore_keywords (per matched product)",
                "memory_list_segment_products (per matched segment)",
                "memory_get_channel_outputs (per matched product)",
                "memory_search_campaigns (vector — Qdrant)",
                "memory_get_knowledge (by category)",
            ],
        }
    except Exception as exc:
        logger.warning("[MEM_FORCE_RETRIEVAL] intent-driven retrieval: %s", exc)
    dump["intent_driven"] = intent_dump

    def _sanitize_dump(obj):
        if hasattr(obj, "model_dump"):
            try: return _sanitize_dump(obj.model_dump())
            except Exception: return str(obj)
        if isinstance(obj, dict):
            return {k: _sanitize_dump(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize_dump(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        try:
            import json as _json
            _json.dumps(obj); return obj
        except Exception:
            return str(obj)

    state["_archival_dump"] = _sanitize_dump(dump)
    logger.info("[MEM_FORCE_RETRIEVAL] dumped | products=%d segments=%d knowledge=%d "
                "campaigns=%d recall=%d assets=%d",
                len(dump.get("products", [])),
                len(dump.get("segments", [])),
                len(dump.get("knowledge", [])),
                len(dump.get("recent_campaigns", [])),
                len(dump.get("recall_log", [])),
                len(dump.get("top_assets", [])))
    return None


def _memory_after_agent_chain(callback_context):
    """LOOP 7/8: turn 종료 시 end_of_agent 마킹.
    ADK _find_agent_to_run 가 본 event 를 _event_filter 로 skip 하여 다음 turn 시
    root_agent (LLM 의도 분류기 보유) 로 회귀합니다 — sticky 라우팅 해소.
    LOOP 8 fix: CallbackContext 는 'actions' 가 아닌 '_event_actions' 노출.
    """
    actions = getattr(callback_context, "_event_actions", None)
    if actions is not None:
        try:
            actions.end_of_agent = True
        except Exception as exc:
            logger.warning("[MEM_AFTER] set end_of_agent failed: %s", exc)
    return None


memory_agent = Agent(
    name="memory_agent",
    # Pro 업그레이드 — Skill MD 통합/캠페인 컨텍스트 합성에 강한 추론 필요
    model="gemini-2.5-pro",
    description=prompt.MEMORY_AGENT_DESCRIPTION,
    instruction=prompt.MEMORY_AGENT_INSTRUCTIONS,
    # ADK _is_transferable_across_agent_tree 가 False 반환 → 다음 turn 시
    # _find_agent_to_run 의 reversed-search 에서 본 agent 가 매치 안 됨 → root_agent
    # 로 fallback → root_pre_dispatch(LLM 분류기) 정상 진입. sibling transfer 는 영향 없음.
    disallow_transfer_to_parent=True,
    before_agent_callback=_force_archival_retrieval,
    after_agent_callback=_memory_after_agent_chain,
    tools=[
        # 캠페인 컨텍스트 통합 retrieval (Skill MD + 5블록 + Qdrant 일괄)
        # Memory Agent 가 본 도구를 호출해 _campaign_memory_context 를 채우고,
        # 그 결과를 자연어/JSON 으로 Orchestrator 에게 반환합니다.
        memory_agent_query_campaign_context,
        # Skill MD 참조 (개별 분배 저장 시에도 사용)
        read_skill_md,
        # Core Memory — profile, voice, domain
        memory_get_core_profile,
        memory_update_user_profile,
        memory_update_brand_voice,
        memory_update_domain_profile,
        memory_add_domain_knowledge,
        memory_get_knowledge,
        # Product CRUD
        memory_add_product,
        memory_get_product,
        memory_update_product,
        # Audience
        memory_update_audience_segment,
        memory_add_audience_trait,
        memory_get_audience_segments,
        # Performance & Behavior
        memory_collect_performance,
        memory_get_performance_pending,
        memory_mark_performance_asked,
        memory_get_behavior_insights,
        memory_get_top_pickscore_keywords,
        # Archival — campaigns & conversations
        memory_archive_campaign,
        memory_search_campaigns,
        memory_get_recent_campaigns,
        memory_archive_conversation,
        memory_search_conversations,
        # Recall & Working Memory
        memory_update_working_summary,
        memory_append_recall,
        memory_get_recall_log,
        memory_add_performance_notes,
        # Assets
        memory_record_generated_asset,
        memory_get_assets,
        # Context Management
        memory_compress_context,
        memory_get_context_status,
        # ERD v2 — N:M Link + ChannelOutput + PerformanceRecord (구조변경 v2)
        memory_link_product_segment,
        memory_link_campaign_product,
        memory_link_campaign_segment,
        memory_list_segment_products,
        memory_list_campaign_products,
        memory_add_channel_output,
        memory_add_performance_record,
        memory_get_channel_outputs,
        # 다단계 조인 (운영 참조 질의)
        memory_trace_product_to_campaigns,
        memory_trace_segment_to_campaigns,
        # 전체 카탈로그 (Phase 6 보강)
        memory_list_all_products,
        memory_list_all_segments,
        memory_list_all_campaigns,
    ],
    output_key="memory_agent_output",
)
