import { useState } from 'react';
import { FaFacebook, FaRegThumbsUp, FaRegComment, FaShare } from "react-icons/fa6";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';

interface FacebookBlockProps {
  contentText: string;
  mediaUrl?: string;
  username?: string;
  profilePicUrl?: string;
  timestamp?: string;
}

export default function FacebookPostBlock({
  contentText,
  mediaUrl,
  username = "Brand Page",
  profilePicUrl = "https://via.placeholder.com/40",
  timestamp = "2시간 전",
}: FacebookBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(contentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <BaseBlock
      icon={FaFacebook}
      title="Facebook"
      content={
        <div className="px-3 py-3">
          <div className="relative bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
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
            <div className="flex items-center space-x-2 p-3">
              <img src={profilePicUrl} alt="Profile" className="w-10 h-10 rounded-full" />
              <div>
                <p className="text-sm font-semibold text-blue-600">{username}</p>
                <p className="text-xs text-gray-500">{timestamp} · 🌐</p>
              </div>
            </div>
            <p className="px-3 pb-2 text-sm text-gray-800 whitespace-pre-line">{contentText}</p>
            {mediaUrl && (
              <div className="w-full aspect-video bg-gray-100">
                <img src={mediaUrl} alt="Post" className="w-full h-full object-cover" />
              </div>
            )}
            <div className="flex border-t border-gray-200 divide-x divide-gray-200">
              {[
                { icon: FaRegThumbsUp, label: "좋아요" },
                { icon: FaRegComment, label: "댓글 달기" },
                { icon: FaShare, label: "공유하기" },
              ].map(({ icon: Icon, label }) => (
                <button key={label} className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs text-gray-600 hover:bg-gray-50">
                  <Icon className="text-sm" /> {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      }
    />
  );
}
