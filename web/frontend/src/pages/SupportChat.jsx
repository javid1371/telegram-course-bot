import { useState, useEffect, useRef, useCallback } from 'react';
import { support } from '../api';
import toast from 'react-hot-toast';

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'الان';
  if (mins < 60) return `${mins} دقیقه پیش`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ساعت پیش`;
  const days = Math.floor(hours / 24);
  return `${days} روز پیش`;
}

function formatTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('fa-IR', { month: 'short', day: 'numeric' });
}

export default function SupportChat() {
  const [conversations, setConversations] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [replyText, setReplyText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [totalUnread, setTotalUnread] = useState(0);
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);

  // Load conversations
  const loadConversations = useCallback(async () => {
    try {
      const data = await support.conversations();
      setConversations(data.conversations || []);
      const unread = (data.conversations || []).reduce((sum, c) => sum + (c.unread_count || 0), 0);
      setTotalUnread(unread);
    } catch (e) {
      console.error('Error loading conversations:', e);
    }
  }, []);

  // Load messages for selected user
  const loadMessages = useCallback(async (userId) => {
    if (!userId) return;
    try {
      const data = await support.messages(userId);
      setMessages(data.messages || []);
    } catch (e) {
      toast.error('خطا در دریافت پیام‌ها');
    }
  }, []);

  // Initial load
  useEffect(() => {
    setLoading(true);
    loadConversations().finally(() => setLoading(false));
  }, [loadConversations]);

  // Poll for new messages every 10s
  useEffect(() => {
    pollRef.current = setInterval(() => {
      loadConversations();
      if (selectedUserId) loadMessages(selectedUserId);
    }, 10000);
    return () => clearInterval(pollRef.current);
  }, [selectedUserId, loadConversations, loadMessages]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Select a conversation
  const selectConversation = async (userId) => {
    setSelectedUserId(userId);
    await loadMessages(userId);
    // Refresh conversations to update unread counts
    loadConversations();
  };

  // Send reply
  const handleReply = async (e) => {
    e.preventDefault();
    if (!replyText.trim() || !selectedUserId) return;

    setSending(true);
    try {
      const res = await support.reply(selectedUserId, replyText.trim());
      setReplyText('');
      // Add the new message to the list
      if (res.message) {
        setMessages((prev) => [...prev, res.message]);
      }
      if (res.delivered === false) {
        toast.error(res.detail || 'پیام ذخیره شد اما ارسال نشد');
      }
      loadConversations();
    } catch (e) {
      toast.error(e.message || 'خطا در ارسال پاسخ');
    } finally {
      setSending(false);
    }
  };

  const selectedConv = conversations.find(c => c.user_id === selectedUserId);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">در حال بارگذاری...</div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3rem)]">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-800">
          💬 پشتیبانی
          {totalUnread > 0 && (
            <span className="mr-2 px-2 py-0.5 text-xs bg-red-500 text-white rounded-full">
              {totalUnread}
            </span>
          )}
        </h1>
      </div>

      <div className="flex gap-4 h-[calc(100%-3rem)]">
        {/* Conversations List */}
        <div className="w-80 bg-white rounded-lg shadow overflow-hidden flex flex-col">
          <div className="p-3 bg-slate-50 border-b font-semibold text-sm text-gray-600">
            مکالمات ({conversations.length})
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="p-6 text-center text-gray-400 text-sm">
                هنوز پیامی دریافت نشده
              </div>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.user_id}
                  onClick={() => selectConversation(conv.user_id)}
                  className={`w-full text-right p-3 border-b border-gray-100 transition-colors hover:bg-blue-50 ${
                    selectedUserId === conv.user_id ? 'bg-blue-50 border-r-4 border-r-blue-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm">
                        {conv.platform === 'bale' ? '🅱️' : '✈️'}
                      </div>
                      <div>
                        <div className="font-medium text-sm text-gray-800">
                          {conv.first_name || ''} {conv.last_name || ''}
                        </div>
                        {conv.username && (
                          <div className="text-xs text-gray-400">@{conv.username}</div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className="text-[10px] text-gray-400">
                        {timeAgo(conv.last_message_at)}
                      </span>
                      {conv.unread_count > 0 && (
                        <span className="px-1.5 py-0.5 text-[10px] bg-red-500 text-white rounded-full min-w-[18px] text-center">
                          {conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mt-1 truncate pr-10">
                    {conv.last_sender === 'admin' ? '↩️ ' : ''}
                    {conv.last_message_preview || '...'}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 bg-white rounded-lg shadow overflow-hidden flex flex-col">
          {!selectedUserId ? (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <div className="text-4xl mb-3">💬</div>
                <div>یک مکالمه را انتخاب کنید</div>
              </div>
            </div>
          ) : (
            <>
              {/* Chat Header */}
              <div className="p-3 bg-slate-50 border-b flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm">
                    {selectedConv?.platform === 'bale' ? '🅱️' : '✈️'}
                  </div>
                  <div>
                    <div className="font-semibold text-sm">
                      {selectedConv?.first_name || ''} {selectedConv?.last_name || ''}
                    </div>
                    <div className="text-xs text-gray-400">
                      {selectedConv?.username ? `@${selectedConv.username}` : `ID: ${selectedConv?.telegram_user_id}`}
                      {' · '}
                      {selectedConv?.platform === 'bale' ? 'بله' : 'تلگرام'}
                    </div>
                  </div>
                </div>
                <a
                  href={`/users/${selectedUserId}`}
                  className="text-xs text-blue-500 hover:underline"
                >
                  مشاهده پروفایل ←
                </a>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
                {messages.length === 0 ? (
                  <div className="text-center text-gray-400 text-sm py-8">
                    بدون پیام
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isAdmin = msg.sender_type === 'admin';
                    return (
                      <div
                        key={msg.id}
                        className={`flex ${isAdmin ? 'justify-start' : 'justify-end'}`}
                      >
                        <div
                          className={`max-w-[70%] rounded-lg px-3 py-2 ${
                            isAdmin
                              ? 'bg-blue-100 text-blue-900'
                              : 'bg-white shadow text-gray-800'
                          }`}
                        >
                          {msg.file_type && (
                            <div className="text-xs text-gray-500 mb-1">
                              📎 {msg.file_type === 'photo' ? 'عکس' : msg.file_type === 'video' ? 'ویدیو' : msg.file_type === 'audio' ? 'صوت' : msg.file_type === 'voice' ? 'ویس' : 'فایل'}
                            </div>
                          )}
                          {msg.message_text && (
                            <div className="text-sm whitespace-pre-wrap">{msg.message_text}</div>
                          )}
                          <div className={`text-[10px] mt-1 ${isAdmin ? 'text-blue-400' : 'text-gray-400'}`}>
                            {isAdmin ? '👤 ادمین' : '🧑 کاربر'}
                            {' · '}
                            {formatTime(msg.created_at)}
                            {' · '}
                            {formatDate(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Input */}
              <form onSubmit={handleReply} className="p-3 border-t bg-white flex gap-2">
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="پاسخ خود را بنویسید..."
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  disabled={sending}
                  dir="rtl"
                />
                <button
                  type="submit"
                  disabled={sending || !replyText.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {sending ? '...' : 'ارسال ↩️'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
