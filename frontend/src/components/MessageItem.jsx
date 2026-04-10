import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';
import { motion } from 'framer-motion';

const MessageItem = ({ msg }) => {
  const renderContent = (text = '') => {
    if (!text) return null;
    const videoRegex = /\[PLAY_VIDEO:(https:\/\/[^\]]+)\]/;
    const match = text.match(videoRegex);
    
    if (match) {
      const url = match[1];
      const videoToken = match[0];
      const parts = text.split(videoToken);
      return (
        <div className="flex flex-col gap-4">
          {parts[0] && <ReactMarkdown>{parts[0]}</ReactMarkdown>}
          <div className="w-full max-w-2xl aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl scale-in">
            <iframe width="100%" height="100%" src={url} title="Nexus Video" frameBorder="0" allowFullScreen></iframe>
          </div>
          {parts[1] && <ReactMarkdown>{parts[1]}</ReactMarkdown>}
        </div>
      );
    }
    return <ReactMarkdown>{text}</ReactMarkdown>;
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`message-wrap ${msg.role}`}
    >
      <div className="message-content">
        <div className={`avatar ${msg.role}`}>
          {msg.role === 'bot' ? <Bot size={22} strokeWidth={2.5} /> : <User size={22} strokeWidth={2.5} />}
        </div>
        <div className="text-container">
          {renderContent(msg.text)}
        </div>
      </div>
    </motion.div>
  );
};

export default MessageItem;
