import { useState } from 'react';
import { FaYoutube } from "react-icons/fa6";
import { BsDot } from "react-icons/bs";
import BaseBlock from './base_block';
import { ArrowPathIcon, ClipboardDocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';


interface YouTubeBlockProps {
    videoUrl: string;
    thumbnailUrl: string;
    videoTitle: string;
    channelName: string;
    views?: number;
    uploadTime?: string;
    descriptionSnippet?: string;
}


export default function YouTubePostBlock({
    videoUrl,
    thumbnailUrl,
    videoTitle,
    channelName,
    views = 999,
    uploadTime = "1 day ago",
    descriptionSnippet,
}: YouTubeBlockProps) {
    const [copied, setCopied] = useState(false);

    const copyText = [videoTitle, descriptionSnippet].filter(Boolean).join('\n\n');
    const handleCopy = async () => {
        await navigator.clipboard.writeText(copyText);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    const formattedViews = views.toLocaleString();

    const truncatedVideoTitle = videoTitle.length > 50
        ? videoTitle.substring(0, 50) + '...'
        : videoTitle;

    return (
        <BaseBlock
            icon={FaYoutube}
            title="YouTube"
            content={
                <div className="px-3 py-3">
                    <div className="relative bg-white border border-gray-200 overflow-hidden shadow-sm">
                        {/* Copy / Download buttons */}
                        <div className="absolute top-2 right-2 z-10 flex gap-1">
                            <button onClick={handleCopy} title="Copy text" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                                {copied ? <CheckIcon className="w-3.5 h-3.5 text-emerald-500" /> : <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500" />}
                            </button>
                            {videoUrl && (
                                <a href={videoUrl} target="_blank" rel="noopener noreferrer" title="Download video" className="p-1.5 bg-white/80 backdrop-blur rounded-md shadow-sm hover:bg-white transition-colors">
                                    <ArrowDownTrayIcon className="w-3.5 h-3.5 text-gray-500" />
                                </a>
                            )}
                        </div>
                        <div className="relative w-full aspect-video bg-gray-900 flex items-center justify-center">
                            {videoUrl ? (
                                <video
                                    className="w-full h-full object-cover"
                                    src={videoUrl}
                                    controls
                                    autoPlay
                                    loop
                                />
                            ) : (
                                <div className="flex items-center justify-center w-full h-full">
                                    <ArrowPathIcon className="h-12 w-12 text-gray-500 animate-spin" />
                                </div>
                            )}
                        </div>

                        <div className="p-3 flex space-x-3">
                            {/* Channel Profile Picture */}
                            <img
                                src={thumbnailUrl}
                                alt="Channel Profile"
                                className="w-9 h-9 rounded-full flex-shrink-0"
                            />
                            <div className="flex-1">
                                {/* Video Title */}
                                <h3 className="text-sm font-semibold text-gray-900 leading-snug">
                                    {truncatedVideoTitle}
                                </h3>
                                {/* Channel Name, Views and Upload Time */}
                                <p className="text-xs text-gray-500">
                                    {channelName}<BsDot className="inline-block mx-0.5 align-middle" />{formattedViews} views<BsDot className="inline-block mx-0.5 align-middle" />{uploadTime}
                                </p>
                                {/* Optional Description Snippet */}
                                {descriptionSnippet && (
                                    <p className="text-xs text-gray-700 mt-2 line-clamp-2">
                                        {descriptionSnippet}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            }
        />
    );
}
