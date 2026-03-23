import { useState } from 'react';
import { SiKakaotalk } from "react-icons/si";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';

interface KakaoBlockProps {
  contentText: string;
  mediaUrl?: string;
  title?: string;
  buttonText?: string;
}

export default function KakaoPostBlock({
  contentText,
  mediaUrl,
  title = "카카오 비즈보드",
  buttonText = "자세히 보기",
}: KakaoBlockProps) {
  const [copied, setCopied] = useState(false);

  const copyText = [title, contentText].filter(Boolean).join('\n\n');
  const handleCopy = async () => {
    await navigator.clipboard.writeText(copyText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <BaseBlock
      icon={SiKakaotalk}
      title="Kakao"
      content={
        <div className="px-3 py-3">
          <div className="relative bg-[#FEE500] border border-yellow-300 rounded-2xl overflow-hidden shadow-sm max-w-[280px] mx-auto">
            {/* Copy / Download buttons */}
            <div className="absolute top-2 right-2 z-10 flex gap-1">
              <button onClick={handleCopy} title="Copy text" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                {copied ? <CheckIcon className="w-3.5 h-3.5 text-emerald-500" /> : <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500" />}
              </button>
              {mediaUrl && (
                <a href={mediaUrl} target="_blank" rel="noopener noreferrer" title="Download image" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                  <ArrowDownTrayIcon className="w-3.5 h-3.5 text-gray-500" />
                </a>
              )}
            </div>
            {mediaUrl && (
              <div className="w-full aspect-video bg-gray-100">
                <img src={mediaUrl} alt="Kakao" className="w-full h-full object-cover" />
              </div>
            )}
            <div className="p-4 bg-white rounded-b-2xl">
              <p className="text-sm font-bold text-gray-900 mb-1">{title}</p>
              <p className="text-xs text-gray-600 whitespace-pre-line line-clamp-3">{contentText}</p>
              <button className="mt-3 w-full py-2 bg-[#FEE500] text-sm font-semibold text-gray-900 rounded-lg hover:bg-yellow-400 transition-colors">
                {buttonText}
              </button>
            </div>
          </div>
        </div>
      }
    />
  );
}
