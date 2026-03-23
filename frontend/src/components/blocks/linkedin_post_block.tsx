import { useState } from 'react';
import { FaLinkedinIn, FaRegThumbsUp, FaRegComment } from "react-icons/fa6";
import { FaRetweet } from "react-icons/fa6";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';

interface LinkedInBlockProps {
  contentText: string;
  mediaUrl?: string;
  username?: string;
  headline?: string;
  profilePicUrl?: string;
  timestamp?: string;
}

export default function LinkedInPostBlock({
  contentText,
  mediaUrl,
  username = "Brand Professional",
  headline = "Marketing Manager",
  profilePicUrl = "https://via.placeholder.com/40",
  timestamp = "2시간",
}: LinkedInBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(contentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <BaseBlock
      icon={FaLinkedinIn}
      title="LinkedIn"
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
              <img src={profilePicUrl} alt="Profile" className="w-12 h-12 rounded-full" />
              <div>
                <p className="text-sm font-semibold">{username}</p>
                <p className="text-xs text-gray-500">{headline}</p>
                <p className="text-xs text-gray-400">{timestamp} · 🌐</p>
              </div>
            </div>
            <p className="px-3 pb-3 text-sm text-gray-800 whitespace-pre-line">{contentText}</p>
            {mediaUrl && (
              <div className="w-full aspect-video bg-gray-100">
                <img src={mediaUrl} alt="Post" className="w-full h-full object-cover" />
              </div>
            )}
            <div className="flex border-t border-gray-100 divide-x divide-gray-100 px-2">
              {[
                { icon: FaRegThumbsUp, label: "추천" },
                { icon: FaRegComment, label: "댓글" },
                { icon: FaRetweet, label: "공유" },
              ].map(({ icon: Icon, label }) => (
                <button key={label} className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs text-gray-600 hover:bg-gray-50">
                  <Icon /> {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      }
    />
  );
}
