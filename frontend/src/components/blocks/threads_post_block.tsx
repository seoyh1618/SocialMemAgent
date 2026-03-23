import { useState } from 'react';
import { FaThreads, FaRegHeart, FaRegComment, FaRetweet } from "react-icons/fa6";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';

interface ThreadsBlockProps {
  contentText: string;
  mediaUrl?: string;
  username?: string;
  profilePicUrl?: string;
  timestamp?: string;
}

export default function ThreadsPostBlock({
  contentText,
  mediaUrl,
  username = "brand_account",
  profilePicUrl = "https://via.placeholder.com/32",
  timestamp = "2시간",
}: ThreadsBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(contentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <BaseBlock
      icon={FaThreads}
      title="Threads"
      content={
        <div className="px-3 py-3">
          <div className="relative bg-white border border-gray-200 rounded-lg shadow-sm p-4">
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
            <div className="flex space-x-3">
              <img src={profilePicUrl} alt="Profile" className="w-9 h-9 rounded-full" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{username}</span>
                  <span className="text-xs text-gray-400">{timestamp}</span>
                </div>
                <p className="mt-1 text-sm text-gray-800 whitespace-pre-line">{contentText}</p>
                {mediaUrl && (
                  <div className="mt-2 rounded-lg overflow-hidden border border-gray-100">
                    <img src={mediaUrl} alt="Post" className="w-full object-cover" />
                  </div>
                )}
                <div className="flex gap-4 mt-3 text-gray-400 text-base">
                  <button className="hover:text-red-500"><FaRegHeart /></button>
                  <button className="hover:text-blue-500"><FaRegComment /></button>
                  <button className="hover:text-green-500"><FaRetweet /></button>
                </div>
              </div>
            </div>
          </div>
        </div>
      }
    />
  );
}
