import { useState } from 'react';
import { FaInstagram, FaRegHeart, FaRegComment, FaRegPaperPlane, FaRegBookmark } from "react-icons/fa6";
import { BsThreeDots } from "react-icons/bs";
import BaseBlock from './base_block';
import { ArrowPathIcon, ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';


interface InstagramBlockProps {
    mediaUrl: string;
    contentText: string;
    username?: string;
    profilePicUrl?: string;
    likesCount?: number;
    timestamp?: string;
}

export default function InstagramBlock({
    mediaUrl, // Video or Image Url
    contentText,
    username = "username",
    profilePicUrl = "https://via.placeholder.com/32",
    likesCount = 1234,
    timestamp = "2 hours ago",
}: InstagramBlockProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(contentText);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <BaseBlock
            icon={FaInstagram}
            title="Instagram"
            content={
                <div className="px-3 py-3">
                    <div className="relative bg-white border border-gray-300 rounded-lg overflow-hidden shadow-sm">
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
                        {/* Post Header: Profile Pic, Username, and original menu button */}
                        <div className="flex items-center justify-between p-3">
                            <div className="flex items-center space-x-2">
                                <img
                                    src={profilePicUrl}
                                    alt="Profile"
                                    className="w-8 h-8 rounded-full"
                                />
                                <span className="text-sm font-semibold">{username}</span>
                            </div>
                            {/* The original Instagram post '...' menu, separate from the block's main menu */}
                            <button className="text-gray-500 text-lg">
                                <BsThreeDots />
                            </button>
                        </div>

                        {/* Video/Image Content */}
                        <div className="w-full aspect-square bg-black flex items-center justify-center">
                            {mediaUrl ? (
                                <img
                                    className="w-full h-full object-cover"
                                    src={mediaUrl}
                                    alt="Post image."
                                />
                            ) : (
                                <div className="flex items-center justify-center w-full h-full">
                                    <ArrowPathIcon className="h-12 w-12 text-gray-500 animate-spin" />
                                </div>
                            )}
                        </div>

                        {/* Post Actions */}
                        <div className="flex justify-between px-3 py-2 text-gray-700 text-xl">
                            <div className="flex space-x-3">
                                <button><FaRegHeart /></button>
                                <button><FaRegComment /></button>
                                <button><FaRegPaperPlane /></button>
                            </div>
                            <button><FaRegBookmark /></button>
                        </div>

                        {/* Like Count */}
                        <p className="px-3 text-sm font-semibold">{likesCount.toLocaleString()} likes</p>

                        {/* Post Caption */}
                        <p className="px-3 pb-2 text-sm">
                            <span className="font-semibold">{username}</span> {contentText}
                        </p>

                        {/* Timestamp */}
                        <p className="px-3 pb-3 text-xs text-gray-500">{timestamp}</p>
                    </div>
                </div>
            }
        />
    );
}
