import { useState } from 'react';
import { FaXTwitter, FaRegComment, FaRetweet, FaRegHeart, FaShareFromSquare } from "react-icons/fa6";
import { BsDot } from "react-icons/bs";
import BaseBlock from './base_block';
import { ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';


interface TwitterBlockProps {
    profilePicUrl?: string;
    username?: string;
    handle?: string;
    contentText: string;
    mediaUrl?: string; // Optional image/video in the tweet
    timestamp?: string;
    commentsCount?: number;
    retweetsCount?: number;
    likesCount?: number;
}


export default function TwitterPostBlock({
    profilePicUrl = "https://via.placeholder.com/40",
    username = "Username",
    handle = "@handle",
    contentText,
    mediaUrl,
    timestamp = "1h",
    commentsCount = 23,
    retweetsCount = 45,
    likesCount = 120,
}: TwitterBlockProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(contentText);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <BaseBlock
            icon={FaXTwitter}
            title="X"
            content={
                <div className="px-3 py-3">
                    <div className="relative bg-white border border-gray-200 rounded-lg shadow-sm p-4">
                        {/* Copy / Download buttons */}
                        <div className="absolute top-2 right-2 z-10 flex gap-1">
                            <button onClick={handleCopy} title="Copy text" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                                {copied ? <CheckIcon className="w-3.5 h-3.5 text-emerald-500" /> : <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500" />}
                            </button>
                            {mediaUrl && (
                                <a href={mediaUrl} target="_blank" rel="noopener noreferrer" title="Download media" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                                    <ArrowDownTrayIcon className="w-3.5 h-3.5 text-gray-500" />
                                </a>
                            )}
                        </div>
                        <div className="flex space-x-3 ]">
                            {/* Profile Picture */}
                            <img
                                src={profilePicUrl}
                                alt="Profile"
                                className="w-10 h-10 rounded-full"
                            />
                            <div className="flex-1">
                                {/* Username, Handle, Timestamp */}
                                <div className="flex items-center text-sm">
                                    <span className="font-bold text-gray-900">{username}</span>
                                    <BsDot className="mx-0.5 text-gray-500" />
                                    <span className="text-gray-500">{handle}</span>
                                    <BsDot className="mx-0.5 text-gray-500" />
                                    <span className="text-gray-500">{timestamp}</span>
                                </div>

                                {/* Tweet Content Text */}
                                {contentText === "" ? (
                                    <div className="flex space-x-1 mt-2 min-h-10">
                                        <span className="h-2 w-2 bg-gray-400 rounded-full animate-pulse [animation-delay:-0.3s]"></span>
                                        <span className="h-2 w-2 bg-gray-400 rounded-full animate-pulse [animation-delay:-0.15s]"></span>
                                        <span className="h-2 w-2 bg-gray-400 rounded-full animate-pulse"></span>
                                    </div>
                                ) : (
                                    <p className="mt-1 text-gray-800 text-sm">
                                        {contentText}
                                    </p>
                                )}

                                {/* Optional Media */}
                                {mediaUrl && (
                                    <div className="mt-3 rounded-lg overflow-hidden border border-gray-200">
                                        <video
                                            className="w-full h-full object-cover"
                                            src={mediaUrl}
                                            controls
                                            autoPlay
                                            loop
                                        />
                                    </div>
                                )}

                                {/* Action Buttons */}
                                <div className="flex justify-between mt-3 text-gray-500 text-base">
                                    <button className="flex items-center space-x-1 hover:text-blue-500">
                                        <FaRegComment />
                                        <span className="text-xs">{commentsCount}</span>
                                    </button>
                                    <button className="flex items-center space-x-1 hover:text-green-500">
                                        <FaRetweet />
                                        <span className="text-xs">{retweetsCount}</span>
                                    </button>
                                    <button className="flex items-center space-x-1 hover:text-red-500">
                                        <FaRegHeart />
                                        <span className="text-xs">{likesCount}</span>
                                    </button>
                                    <button className="hover:text-blue-500">
                                        <FaShareFromSquare />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            }
        />
    );
}
