import { useState } from 'react';
import { FaPinterest } from "react-icons/fa6";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';

interface PinterestBlockProps {
  mediaUrl: string;
  title?: string;
  description?: string;
  boardName?: string;
}

export default function PinterestPostBlock({
  mediaUrl,
  title = "Pin Title",
  description = "",
  boardName = "Brand Board",
}: PinterestBlockProps) {
  const [copied, setCopied] = useState(false);

  const copyText = [title, description].filter(Boolean).join('\n\n');
  const handleCopy = async () => {
    await navigator.clipboard.writeText(copyText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <BaseBlock
      icon={FaPinterest}
      title="Pinterest"
      content={
        <div className="px-3 py-3">
          <div className="relative bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm max-w-[240px] mx-auto">
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
            <div className="w-full aspect-[2/3] bg-gray-100">
              {mediaUrl ? (
                <img src={mediaUrl} alt="Pin" className="w-full h-full object-cover" />
              ) : (
                <div className="flex items-center justify-center w-full h-full text-gray-400 text-sm">이미지 생성 중...</div>
              )}
            </div>
            <div className="p-3">
              <p className="text-sm font-semibold text-gray-900 line-clamp-2">{title}</p>
              {description && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{description}</p>}
              <p className="text-xs text-gray-400 mt-2">📌 {boardName}</p>
            </div>
            <div className="flex border-t border-gray-100 divide-x divide-gray-100">
              <button className="flex-1 py-2 text-xs text-center text-red-600 font-medium hover:bg-red-50">저장</button>
              <button className="flex-1 py-2 text-xs text-center text-gray-600 hover:bg-gray-50">방문</button>
            </div>
          </div>
        </div>
      }
    />
  );
}
