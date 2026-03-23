import { PaperAirplaneIcon, ChevronRightIcon, ChevronDownIcon, PhotoIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { useState, useRef, useEffect } from 'react';
import { sendMessageToAgentSSE, extractTextFromResponse } from '../api';
import type { Base, SocialMediaAgentOutput, OrchestratorChannelOutput } from '../base';
import { channelsToBase } from '../base';
import type { Dispatch, SetStateAction } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';

const markdownComponents: Components = {
  a: ({children, ...props}: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props} className="text-blue-500 underline">
      {children}
    </a>
  ),
};

interface Message {
  // Role determines how the message is rendered.
  // `base_content` is not rendered as a chat bubble but as a "Restore" button.
  // `memory_ref` is rendered as an inline chip showing which memory tools were used.
  role: 'user' | 'reasoning' | 'base_content' | 'agent' | 'memory_ref';
  content: string;
  isComplete?: boolean;
}

// Define props interface
interface ChatInterfaceProps {
  userId: string;
  sessionId: string;
  base: Base;
  setBase: Dispatch<SetStateAction<Base>>;
  shouldStartGeneration?: boolean;
}

export default function ChatInterface({ userId, sessionId, base, setBase, shouldStartGeneration }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [reasoningCollapsed, setReasoningCollapsed] = useState<Record<number, boolean>>({});
  const lastChunkId = useRef<string | null>(null);
  const formattedBaseContent = useRef('');
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [attachedImage, setAttachedImage] = useState<{ preview: string; mimeType: string; data: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasStartedGeneration = useRef(false);
  const imageFileInputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom whenever messages change
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Trigger generation when shouldStartGeneration is true
  useEffect(() => {
    if (shouldStartGeneration && !hasStartedGeneration.current) {
      const startGeneration = async () => {
        try {
          await sendMessage("Start the generation.");
        } catch (error) {
          console.error("Failed to start generation:", error);
        }
      };
      
      startGeneration();
      hasStartedGeneration.current = true;
    }
  }, [shouldStartGeneration]);

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      // dataUrl is like "data:image/jpeg;base64,..."
      const [header, data] = dataUrl.split(',');
      const mimeType = header.match(/data:([^;]+)/)?.[1] || 'image/jpeg';
      setAttachedImage({ preview: dataUrl, mimeType, data });
    };
    reader.readAsDataURL(file);
    // Reset so same file can be re-selected
    e.target.value = '';
  };

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    // Capture current image before clearing it
    const currentImage = attachedImage;

    // Add user message (with image preview if attached)
    const userMessage: Message = { role: 'user' as const, content: messageText, isComplete: true };
    setMessages(prev => [...prev, userMessage]);
    if (currentImage) {
      const imageMessage: Message = { role: 'user' as const, content: `![attached](${currentImage.preview})`, isComplete: true };
      setMessages(prev => [...prev, imageMessage]);
      setAttachedImage(null);
    }

    // Create placeholder for agent's reasoning
    const reasoningPlaceholder: Message = { role: 'reasoning' as const, content: '', isComplete: false };
    setMessages(prev => [...prev, reasoningPlaceholder]);

    setIsLoading(true);
    formattedBaseContent.current = ''; // Reset for new message

    // Send message to agent (pass attached image if present)
    const cleanup = sendMessageToAgentSSE(
      messageText,
      base,      // Use prop
      userId,    // Use prop
      sessionId, // Use prop
      {
        // callbacks below
        onMemoryToolCall: (toolName) => {
          // Show memory tool calls as both memory_ref chip AND reasoning step
          setMessages(prev => {
            const newMessages = [...prev];
            // Add to memory ref chip
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage?.role === 'memory_ref') {
              const updatedMemRef = { ...lastMessage, content: lastMessage.content + ', ' + toolName };
              newMessages[newMessages.length - 1] = updatedMemRef;
            } else {
              newMessages.push({ role: 'memory_ref', content: toolName, isComplete: true });
            }
            // Also add to reasoning
            const lastReasoning = newMessages.findLastIndex(m => m.role === 'reasoning');
            if (lastReasoning >= 0 && !newMessages[lastReasoning].isComplete) {
              const updated = { ...newMessages[lastReasoning] };
              const displayName = toolName.replace(/^memory_/, '').replace(/_/g, ' ');
              updated.content += `\n🔍 **메모리 조회**: ${displayName}`;
              newMessages[lastReasoning] = updated;
            }
            return newMessages;
          });
        },
        onToolCall: (toolName, author) => {
          // Show all tool calls (strategists, generators, etc.) in reasoning
          setMessages(prev => {
            const newMessages = [...prev];
            const lastReasoning = newMessages.findLastIndex(m => m.role === 'reasoning');
            if (lastReasoning >= 0 && !newMessages[lastReasoning].isComplete) {
              const updated = { ...newMessages[lastReasoning] };
              const displayName = toolName.replace(/_/g, ' ');
              const agentLabel = author?.replace(/_/g, ' ').replace(/agent/gi, '').trim() || '';
              updated.content += `\n⚡ **${agentLabel ? agentLabel + ' → ' : ''}${displayName}**`;
              newMessages[lastReasoning] = updated;
            }
            return newMessages;
          });
        },
        onData: (response) => {
          const text = extractTextFromResponse(response);
          const author = response.author;
          const chunkId = response.id;

          if (!text || lastChunkId.current === chunkId) return;
          lastChunkId.current = chunkId;

          // Determine if this is a "final" agent response or intermediate reasoning
          const isFinalAgent = author === "general_chat_agent" || author === "content_orchestrator";
          const isReasoning = author?.endsWith("_strategist") ||
                              author === "idea_generation_agent" ||
                              author === "image_generation_agent" ||
                              author === "video_generation_agent" ||
                              author === "audio_generation_agent" ||
                              author === "format_agent" ||
                              author === "response_agent";

          if (isFinalAgent) {
            setMessages(prev => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage?.role === 'agent' && !lastMessage.isComplete) {
                const updatedAgentMessage = { ...lastMessage, content: lastMessage.content + text };
                return [...prev.slice(0, -1), updatedAgentMessage];
              }
              const newAgentMessage: Message = { role: 'agent', content: text, isComplete: false };
              return [...prev, newAgentMessage];
            });
          } else if (isReasoning && text.trim()) {
            // Show intermediate agent steps as reasoning
            const stepLabel = author?.replace(/_/g, ' ').replace(/agent|strategist/gi, '').trim() || 'processing';
            setMessages(prev => {
              // Find the reasoning placeholder or last reasoning message
              const lastReasoning = prev.findLastIndex(m => m.role === 'reasoning');
              if (lastReasoning >= 0 && !prev[lastReasoning].isComplete) {
                const updated = { ...prev[lastReasoning] };
                updated.content += `\n**[${stepLabel}]** ${text.substring(0, 200)}${text.length > 200 ? '...' : ''}`;
                const newMessages = [...prev];
                newMessages[lastReasoning] = updated;
                return newMessages;
              }
              return prev;
            });
          }
        },
        onError: (error) => {
          console.error('Error from agent:', error);
          setMessages(prev => [
            ...prev,
            { role: 'agent', content: 'Sorry, I encountered an error. Please try again.', isComplete: true }
          ]);
          setIsLoading(false);
        },
        onComplete: () => {
          setMessages(prev => {
            const newMessages = [...prev];

            // Mark all reasoning as complete
            for (const msg of newMessages) {
              if (msg.role === 'reasoning' && !msg.isComplete) {
                msg.isComplete = true;
              }
            }

            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage.role === 'agent') {
              lastMessage.isComplete = true;

              // Try to parse orchestrator channels JSON from agent message
              try {
                const content = lastMessage.content.trim();
                // Try direct JSON parse first (entire content is JSON)
                let parsed: OrchestratorChannelOutput | null = null;

                // Strip markdown code fences if present
                let jsonStr = content;
                if (jsonStr.startsWith('```json')) {
                  jsonStr = jsonStr.replace(/^```json\s*/, '').replace(/\s*```$/, '');
                } else if (jsonStr.startsWith('```')) {
                  jsonStr = jsonStr.replace(/^```\s*/, '').replace(/\s*```$/, '');
                }

                // Try parsing the whole content
                try {
                  const obj = JSON.parse(jsonStr);
                  if (obj.channels && typeof obj.channels === 'object') {
                    parsed = obj;
                  }
                } catch {
                  // Try finding JSON within mixed content
                  const braceStart = content.indexOf('{');
                  const braceEnd = content.lastIndexOf('}');
                  if (braceStart >= 0 && braceEnd > braceStart) {
                    try {
                      const obj = JSON.parse(content.substring(braceStart, braceEnd + 1));
                      if (obj.channels && typeof obj.channels === 'object') {
                        parsed = obj;
                      }
                    } catch { /* not valid JSON */ }
                  }
                }

                if (parsed) {
                  // Schedule base update outside of setMessages
                  setTimeout(() => {
                    setBase(prevBase => channelsToBase(parsed!, prevBase));
                  }, 0);
                  // Replace raw JSON with agent_response text only
                  if (parsed.agent_response) {
                    lastMessage.content = parsed.agent_response;
                  }
                }
              } catch {
                // Not a channels JSON — normal text response, do nothing
              }
            }
            return newMessages;
          });
          setIsLoading(false);
        }
      },
      currentImage ? { mimeType: currentImage.mimeType, data: currentImage.data } : undefined
    );

    // Cleanup on component unmount
    return cleanup;
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    await sendMessage(inputMessage);
    setInputMessage('');
  };

  return (
    <div className="flex h-full flex-col">
      {/* Conversation History */}
      <div className="flex-grow overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.map((message, index) => {
          if (message.role === 'reasoning') {
            if (!message.content.trim()) return null; // Don't render empty reasoning
            const isCollapsed = reasoningCollapsed[index] ?? true;
            return (
              <div key={index} className="w-full my-2 text-gray-500">
                <button
                  onClick={() =>
                    setReasoningCollapsed((prev) => ({
                      ...prev,
                      [index]: !isCollapsed,
                    }))
                  }
                  className="flex items-center text-sm font-medium hover:text-gray-700"
                >
                  {isCollapsed ? (
                    <ChevronRightIcon className="h-4 w-4 mr-1" />
                  ) : (
                    <ChevronDownIcon className="h-4 w-4 mr-1" />
                  )}
                  <span>✨ 사고 과정</span>
                  {!message.isComplete && (
                    <span className="ml-2 text-xs text-indigo-500 animate-pulse">처리 중...</span>
                  )}
                </button>
                {!isCollapsed && (
                  <div className="mt-1 p-3 text-sm text-gray-600 border-l-2 border-indigo-200 ml-2 pl-3 whitespace-pre-wrap bg-gray-50 rounded-r-lg">
                    <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
                    {!message.isComplete && (
                      <span className="inline-block animate-pulse">▋</span>
                    )}
                  </div>
                )}
              </div>
            );
          }
          if (message.role === 'memory_ref') {
            return (
              <div key={index} className="w-full my-1 flex justify-start">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">
                  📚 참조된 메모리: {message.content}
                </span>
              </div>
            );
          }
          if (message.role === 'base_content') {
            if (!message.isComplete) return null; // Don't render while streaming
            return (
              <div key={index} className="w-full my-2 flex justify-start">
                <button
                  onClick={() => {
                    try {
                      const jsonString = message.content
                        .replace(/^```json/, "")
                        .replace(/```$/, "");
                      const agent_output: SocialMediaAgentOutput = JSON.parse(jsonString);
                      if (agent_output.is_updated) {
                        console.log("Setting base to: ", agent_output.updated_base);
                        setBase(agent_output.updated_base);
                      }
                    } catch (e) {
                      console.error("Failed to parse and set base from checkpoint", e);
                    }
                  }}
                  className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 text-sm font-medium"
                >
                  Restore Checkpoint
                </button>
              </div>
            );
          }
          return (
            <div
              key={index}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`rounded-lg p-3 text-sm max-w-[80%] ${
                  message.role === 'user'
                    ? 'bg-indigo-500 text-white'
                    : 'bg-gray-200 text-gray-900'
                }`}
              >
                <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
                {!message.isComplete && (
                  <span className="inline-block animate-pulse">▋</span>
                )}
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white p-4">
        {/* Image preview */}
        {attachedImage && (
          <div className="mb-2 relative inline-block">
            <img src={attachedImage.preview} alt="Attached" className="h-16 w-16 object-cover rounded-md border border-gray-200" />
            <button
              type="button"
              onClick={() => setAttachedImage(null)}
              className="absolute -top-1 -right-1 bg-gray-700 text-white rounded-full p-0.5 hover:bg-gray-900"
            >
              <XMarkIcon className="h-3 w-3" />
            </button>
          </div>
        )}
        <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
          <input
            ref={imageFileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleImageSelect}
          />
          <button
            type="button"
            onClick={() => imageFileInputRef.current?.click()}
            disabled={isLoading}
            className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white p-2 text-gray-500 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
          >
            <PhotoIcon className="size-5" aria-hidden="true" />
            <span className="sr-only">Attach image</span>
          </button>
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-grow rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className={`inline-flex items-center justify-center rounded-md border border-transparent ${
              isLoading || !inputMessage.trim()
                ? 'bg-indigo-300 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700'
            } p-2 text-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2`}
          >
            <PaperAirplaneIcon className="size-5" aria-hidden="true" />
            <span className="sr-only">Send message</span>
          </button>
        </form>
      </div>
    </div>
  );
} 