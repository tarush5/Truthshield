import React, { useCallback, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Upload, FileText, Image, Music, Video, Link2, X } from 'lucide-react';

const FILE_ICONS = {
  text: FileText,
  image: Image,
  audio: Music,
  video: Video,
};

function getFileType(file) {
  const mime = file.type || '';
  if (mime.startsWith('image/')) return 'image';
  if (mime.startsWith('audio/')) return 'audio';
  if (mime.startsWith('video/')) return 'video';
  return 'text';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export default function UploadZone({ onFileSelect, onUrlSubmit, onTextSubmit, disabled = false }) {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [mode, setMode] = useState('upload'); // upload | url | text
  const fileInputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);
      onFileSelect?.(files[0]);
    }
  }, [onFileSelect]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect?.(file);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const modes = [
    { id: 'upload', icon: Upload, label: 'Upload' },
    { id: 'url', icon: Link2, label: 'URL' },
    { id: 'text', icon: FileText, label: 'Text' },
  ];

  return (
    <div className="space-y-4">
      {/* Mode Tabs */}
      <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1 w-fit">
        {modes.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            disabled={disabled}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              mode === id
                ? 'bg-brand-500/20 text-brand-400 shadow-sm'
                : 'text-white/40 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Upload Mode */}
      {mode === 'upload' && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
          className={`relative cursor-pointer rounded-2xl border-2 border-dashed transition-all duration-300 ${
            disabled ? 'opacity-50 cursor-not-allowed' : ''
          } ${
            isDragging
              ? 'border-brand-400 bg-brand-500/10 scale-[1.01]'
              : selectedFile
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept="image/*,audio/*,video/*,.txt,.pdf,.doc,.docx"
            disabled={disabled}
          />

          {selectedFile ? (
            <div className="flex items-center gap-4 p-6">
              {(() => {
                const ft = getFileType(selectedFile);
                const Icon = FILE_ICONS[ft] || FileText;
                return (
                  <div className="w-14 h-14 rounded-xl bg-brand-500/10 flex items-center justify-center">
                    <Icon className="w-7 h-7 text-brand-400" />
                  </div>
                );
              })()}
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{selectedFile.name}</p>
                <p className="text-white/40 text-sm">{formatSize(selectedFile.size)} · {getFileType(selectedFile)}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); clearFile(); }}
                className="p-2 rounded-lg bg-white/5 hover:bg-red-500/10 text-white/30 hover:text-red-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 px-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500/20 to-cyan-500/20 flex items-center justify-center mb-4">
                <Upload className="w-8 h-8 text-brand-400" />
              </div>
              <p className="text-white/70 font-medium mb-1">{t('analyze.drop_zone')}</p>
              <p className="text-white/30 text-sm">{t('analyze.drop_hint')}</p>
              <div className="flex items-center gap-3 mt-4">
                {Object.entries(FILE_ICONS).map(([type, Icon]) => (
                  <div key={type} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 text-white/30 text-xs">
                    <Icon className="w-3.5 h-3.5" />
                    {type}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* URL Mode */}
      {mode === 'url' && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-3">
            <Link2 className="w-5 h-5 text-brand-400 flex-shrink-0" />
            <input
              type="url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); onUrlSubmit?.(e.target.value); }}
              placeholder={t('analyze.url_placeholder')}
              className="input-field"
              disabled={disabled}
            />
          </div>
        </div>
      )}

      {/* Text Mode */}
      {mode === 'text' && (
        <div className="glass-card p-5">
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); onTextSubmit?.(e.target.value); }}
            placeholder={t('analyze.text_placeholder')}
            rows={6}
            className="input-field resize-none"
            disabled={disabled}
          />
          <p className="mt-2 text-xs text-white/20 text-right">{text.length} characters</p>
        </div>
      )}
    </div>
  );
}
