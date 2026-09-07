import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as CodeHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  GitBranch, Search, Cpu, FileText, Code, ShieldCheck,
  Sparkles, RefreshCw, Send, Layers, Folder, FileCode,
  CornerDownRight, Clock,
  Maximize2, RotateCcw, ZoomIn, ZoomOut, X, Star,
  SlidersHorizontal, Plus,
  ChevronDown, User, Bookmark, BookmarkCheck,
  ChevronUp, Network
} from 'lucide-react';

import { API_BASE, GUEST_USER } from './config';
import mermaid, { buildMermaidFromGraph } from './lib/mermaid';
import { languageFromFilePath } from './lib/language';
import { suggestedQuestions } from './lib/suggestions';
import { MarkdownWithCode } from './components/CodeBlock';


function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [repoStars, setRepoStars] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);

  // ⭐ Favorites state with localStorage sync
  const [favorites, setFavorites] = useState(() => {
    const saved = localStorage.getItem('codetrace_favorites');
    return saved ? JSON.parse(saved) : [];
  });

  const toggleFavorite = () => {
    if (!repoUrl) return;
    let updated;
    if (favorites.includes(repoUrl)) {
      updated = favorites.filter((f) => f !== repoUrl);
    } else {
      updated = [...favorites, repoUrl];
    }
    setFavorites(updated);
    localStorage.setItem('codetrace_favorites', JSON.stringify(updated));
  };

  // 🔔 Toast Notifications (replaces native alert())
  const [toast, setToast] = useState(null); // { message, type: 'error' | 'success' }

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // 🌳 Which architecture layers are expanded to show their individual files.
  // Keyed by the layer names the backend returns for the analyzed repo.
  const [expandedNodes, setExpandedNodes] = useState({});
  
  const [fileList, setFileList] = useState([]);
  const [fileSearch, setFileSearch] = useState('');
  const [query, setQuery] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [referencedFiles, setReferencedFiles] = useState([]);

  const [activeTab, setActiveTab] = useState('diagram');
  const [activeSidebarView, setActiveSidebarView] = useState('files');
  const [readmeMarkdown, setReadmeMarkdown] = useState('');
  const [isGeneratingReadme, setIsGeneratingReadme] = useState(false);
  const [svgContent, setSvgContent] = useState('');

  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [isMaximized, setIsMaximized] = useState(false);

  // 📝 Resizable Panel Width State (Percentage)
  const [leftPanelWidth, setLeftPanelWidth] = useState(36);
  const [isResizing, setIsResizing] = useState(false);

  // 📝 Multi-Tab Code Editor State
  const [openTabs, setOpenTabs] = useState([]);
  const [activeTabFile, setActiveTabFile] = useState(null);
  const [fileContents, setFileContents] = useState({});
  const [isCopied, setIsCopied] = useState(false);

  // 🔍 Guardrails Modal
  const [showGuardrailsModal, setShowGuardrailsModal] = useState(false);

  const diagramContainerRef = useRef(null);

  // 🔐 Auth & User State
  //
  // The session token is the source of truth, not this cached user object: the
  // backend re-validates the token on every protected call, so editing
  // localStorage by hand buys nothing.
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('codetrace_token') || '');
  const [user, setUser] = useState(GUEST_USER);
  // Nothing works without a session, so ask for one on arrival rather than
  // letting the first click fail with an authorization error.
  const [showLoginModal, setShowLoginModal] = useState(() => !localStorage.getItem('codetrace_token'));
  const [authMode, setAuthMode] = useState('login');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [savedRepos, setSavedRepos] = useState(() => {
    const saved = localStorage.getItem('codetrace_saved_repos');
    return saved ? JSON.parse(saved) : [];
  });
  const [showProfileModal, setShowProfileModal] = useState(false);

  const chatEndRef = useRef(null);

  const suggestions = suggestedQuestions(analyzeResult?.node_details);

  const signOutLocally = useCallback(() => {
    setAuthToken('');
    setUser(GUEST_USER);
    localStorage.removeItem('codetrace_token');
  }, []);

  // Every protected call goes through here so a session that expired or was
  // revoked server-side drops the UI back to signed-out instead of leaving a
  // stale "logged in" shell behind.
  const authFetch = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...(options.headers || {}), Authorization: `Bearer ${authToken}` }
    });
    if (response.status === 401) {
      signOutLocally();
      setShowLoginModal(true);
      throw new Error('unauthorized');
    }
    return response;
  }, [authToken, signOutLocally]);

  // Confirm a stored token is still valid before showing the user as signed in.
  useEffect(() => {
    // No token means signed out, and both the initial state and signOutLocally
    // already leave `user` as GUEST_USER -- nothing to synchronise here.
    if (!authToken) return;

    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/me`, {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        if (cancelled) return;
        if (!response.ok) {
          signOutLocally();
          return;
        }
        const data = await response.json();
        setUser({ loggedIn: true, name: data.user.name, email: data.user.email, avatar: '💻' });
      } catch {
        // Backend down: keep the token so a later reload can revalidate it.
        if (!cancelled) setUser(GUEST_USER);
      }
    })();
    return () => { cancelled = true; };
  }, [authToken, signOutLocally]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isAsking]);

  // Dynamic Mermaid Graph Generator -- redrawn locally whenever a layer is
  // expanded or collapsed, so toggling detail needs no server round-trip.
  useEffect(() => {
    if (activeTab !== 'diagram') return;

    const diagramCode = analyzeResult?.graph
      ? buildMermaidFromGraph(analyzeResult.graph, expandedNodes)
      : analyzeResult?.mermaid_code;

    if (!diagramCode) return;

    let isMounted = true;
    const renderSvg = async () => {
      try {
        const uniqueId = `mermaid-svg-${Date.now()}`;
        const { svg } = await mermaid.render(uniqueId, diagramCode);
        const cleanedSvg = svg
          .replace(/width="[^"]*"/, 'width="100%"')
          .replace(/height="[^"]*"/, '')
          .replace(/style="[^"]*"/, 'style="width: 100%; height: auto; background: transparent;"');
        if (isMounted) setSvgContent(cleanedSvg);
      } catch (err) {
        console.error("Mermaid Render Error:", err);
      }
    };
    renderSvg();
    return () => { isMounted = false; };
  }, [activeTab, analyzeResult, expandedNodes]);

  // Mermaid Diagram SVG Sizing Effect
  //
  // Mermaid emits a viewBox, so width:100% ENLARGES the drawing to fill the
  // panel -- a three-box diagram ended up looking enormous. Capping the width
  // at its natural size lets it shrink in a narrow panel but never blow up.
  useEffect(() => {
    if (!svgContent || !diagramContainerRef.current) return;

    const svgEl = diagramContainerRef.current.querySelector('svg');
    if (!svgEl) return;

    const viewBoxWidth = parseFloat((svgEl.getAttribute('viewBox') || '').split(/\s+/)[2]);

    svgEl.setAttribute('width', '100%');
    svgEl.removeAttribute('height');
    svgEl.style.height = 'auto';
    svgEl.style.minHeight = '';
    svgEl.style.display = 'block';
    svgEl.style.margin = '0 auto';
    svgEl.style.maxWidth = Number.isFinite(viewBoxWidth) ? `${viewBoxWidth}px` : '100%';
  }, [svgContent]);

  const toggleNodeExpansion = (nodeKey) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeKey]: !prev[nodeKey] }));
  };

  // Clicking a collapsed layer box in the SVG expands it into its files.
  useEffect(() => {
    if (activeTab !== 'diagram' || !diagramContainerRef.current) return;

    const layerNames = (analyzeResult?.graph?.layers || []).map((l) => l.name);
    if (layerNames.length === 0) return;

    diagramContainerRef.current.querySelectorAll('.node').forEach((nodeEl) => {
      const label = nodeEl.textContent || '';
      const matched = layerNames.find((name) => label.includes(name));
      nodeEl.style.cursor = matched ? 'pointer' : 'default';
      nodeEl.onclick = matched ? () => toggleNodeExpansion(matched) : null;
    });
  }, [svgContent, activeTab, analyzeResult]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsMaximized(false);
        setShowGuardrailsModal(false);
        setShowProfileModal(false);
        setShowLoginModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // ↔️ Resizable Panel Logic
  const handleMouseDownResizer = () => {
    setIsResizing(true);
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      const totalWidth = window.innerWidth - 300;
      const mouseX = e.clientX - 300;
      const newWidthPercent = Math.min(85, Math.max(15, (mouseX / totalWidth) * 100));
      setLeftPanelWidth(newWidthPercent);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const handleOpenFileTab = async (filePath) => {
    if (!openTabs.includes(filePath)) {
      setOpenTabs((prev) => [...prev, filePath]);
    }
    setActiveTabFile(filePath);

    if (!fileContents[filePath]) {
      try {
        const response = await authFetch(`/api/file-content?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();
        if (data.content) {
          setFileContents((prev) => ({ ...prev, [filePath]: data.content }));
          return;
        }
      } catch (err) {
        console.error("Failed to fetch file content:", err);
      }

      const fallbackCode = `# File: ${filePath}\n\nimport os\nimport sys\n\ndef main():\n    print("Codetrace active AST inspection for ${filePath}")\n\nif __name__ == '__main__':\n    main()`;
      setFileContents((prev) => ({ ...prev, [filePath]: fallbackCode }));
    }
  };

  const handleCloseTab = (filePath, e) => {
    if (e) e.stopPropagation();
    const filtered = openTabs.filter((t) => t !== filePath);
    setOpenTabs(filtered);
    if (activeTabFile === filePath) {
      setActiveTabFile(filtered.length > 0 ? filtered[filtered.length - 1] : null);
    }
  };

  const handleCopyActiveCode = () => {
    if (activeTabFile && fileContents[activeTabFile]) {
      navigator.clipboard.writeText(fileContents[activeTabFile]);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) return;
    setIsAnalyzing(true);
    try {
      const response = await authFetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl.trim() })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setAnalyzeResult(data);
        if (data.stars !== undefined) {
          setRepoStars(data.stars >= 1000 ? `${(data.stars / 1000).toFixed(1)}k` : `${data.stars}`);
        }
        if (data.file_list && data.file_list.length > 0) setFileList(data.file_list);
        setReadmeMarkdown('');
        setActiveTab('diagram');
        // Writing the README with the LLM takes 2-3 minutes, so it runs in the
        // background and appears in its tab once ready.
        handleGenerateReadme({ background: true });
      } else {
        setToast({ message: "Analysis Error: " + (data.detail || data.message), type: 'error' });
      }
    } catch (err) {
      console.error("Analyze request failed:", err);
      setToast({ message: "Backend server running on port 8000.", type: 'error' });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleToggleFavoriteRepo = () => {
    if (!repoUrl.trim()) return;
    const updated = savedRepos.includes(repoUrl)
      ? savedRepos.filter((r) => r !== repoUrl)
      : [...savedRepos, repoUrl];
    setSavedRepos(updated);
    localStorage.setItem('codetrace_saved_repos', JSON.stringify(updated));
  };

  const [authError, setAuthError] = useState('');
  const [authName, setAuthName] = useState('');

  const handleLoginSubmit = async (e) => {
    if (e) e.preventDefault();
    setAuthError('');
    const endpoint = authMode === 'register' ? '/api/register' : '/api/login';
    const body = authMode === 'register'
      ? { email: loginEmail, password: loginPassword, name: authName }
      : { email: loginEmail, password: loginPassword };

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await response.json();

      if (!response.ok) {
        // FastAPI validation errors return `detail` as an array.
        const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
        setAuthError(detail || 'Something went wrong.');
        return;
      }

      localStorage.setItem('codetrace_token', data.token);
      setAuthToken(data.token);
      setUser({ loggedIn: true, name: data.user.name, email: data.user.email, avatar: '💻' });
      setShowLoginModal(false);
      setLoginEmail('');
      setLoginPassword('');
      setAuthName('');
    } catch (err) {
      console.error("Auth request failed:", err);
      setAuthError('Could not reach the server. Is the backend running?');
    }
  };

  const handleLogout = async () => {
    // Revoke server-side too, otherwise the token stays valid until it expires.
    try {
      await authFetch('/api/logout', { method: 'POST' });
    } catch (err) {
      console.error("Logout request failed:", err);
    }
    signOutLocally();
    setShowProfileModal(false);
  };

  // `presetQuestion` lets a suggestion chip ask directly, without routing the
  // text through the input box first.
  const handleAsk = async (e, presetQuestion) => {
    if (e) e.preventDefault();
    const currentQuery = (presetQuestion ?? query).trim();
    if (!currentQuery || isAsking) return;

    setChatHistory((prev) => [...prev, { sender: 'user', text: currentQuery }]);
    setQuery('');
    setIsAsking(true);

    // Stream the answer in: an empty AI message is appended first, then filled
    // piece by piece so words land on screen as the model produces them.
    let aiMsgIndex = -1;
    setChatHistory((prev) => {
      aiMsgIndex = prev.length;
      return [...prev, { sender: 'ai', answer: '', sources: [], streaming: true }];
    });

    const updateAiMsg = (patch) => {
      setChatHistory((prev) => prev.map((msg, i) => (i === aiMsgIndex ? { ...msg, ...patch } : msg)));
    };

    try {
      const response = await authFetch('/api/ask-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: currentQuery })
      });

      if (!response.ok || !response.body) throw new Error(`Stream failed: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';

      // The server sends NDJSON. Line boundaries do not align with network
      // chunks, so any partial trailing line carries over to the next read.
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.trim()) continue;
          let event;
          try {
            event = JSON.parse(line);
          } catch {
            continue;
          }

          if (event.type === 'meta') {
            updateAiMsg({ confidence_score: event.confidence_score, sources: event.sources || [] });
            if (event.sources?.length > 0) setReferencedFiles(event.sources);
          } else if (event.type === 'text') {
            answer += event.value;
            updateAiMsg({ answer });
          }
        }
      }

      updateAiMsg({ streaming: false });
    } catch (err) {
      console.error("Ask request failed:", err);
      updateAiMsg({ answer: "❌ Could not connect to server.", streaming: false });
    } finally {
      setIsAsking(false);
    }
  };

  // background=true runs quietly right after indexing: it neither switches the
  // user to the README tab nor raises a toast on failure.
  const handleGenerateReadme = async ({ background = false } = {}) => {
    setIsGeneratingReadme(true);
    try {
      const response = await authFetch('/api/generate-readme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setReadmeMarkdown(data.readme_markdown);
        if (!background) setActiveTab('readme');
      } else if (!background) {
        setToast({ message: data.detail || data.message || "Could not generate the README.", type: 'error' });
      }
    } catch (err) {
      console.error("README generation failed:", err);
      if (!background) {
        setToast({ message: "Could not reach the backend. Make sure it is running on http://127.0.0.1:8000", type: 'error' });
      }
    } finally {
      setIsGeneratingReadme(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#090c15] text-slate-100 font-sans overflow-hidden antialiased select-none">

      {/* 🔔 Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-in fade-in slide-in-from-top-2 duration-300 ${
          toast.type === 'error' ? 'bg-rose-600 text-white' : 'bg-emerald-600 text-white'
        }`}>
          {toast.message}
        </div>
      )}

      {/* 🚀 Top Bar Header */}
      <header className="h-14 bg-[#0e121f] border-b border-[#1c2438] px-5 flex items-center justify-between z-20 flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-semibold tracking-wide">Repository URL</span>
            <div className="bg-[#161c2e] border border-[#1c2438] rounded-lg px-3 py-1 flex items-center gap-2.5 w-96 shadow-inner">
              <GitBranch className="w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="bg-transparent text-xs font-mono font-semibold text-white focus:outline-none w-full"
              />
              <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> Active
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-200 font-bold px-3 py-1.5 bg-[#161c2e] border border-[#1c2438] rounded-lg shadow mt-3">
            <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
            <span>{repoStars}</span>
          </div>
        </div>

        {/* Right Header Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !repoUrl.trim()}
            title="Analyze the repository entered above"
            className="flex items-center gap-1.5 bg-[#161c2e] hover:bg-[#20283f] text-slate-200 border border-[#1c2438] text-xs font-bold px-3 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-50"
          >
            {isAnalyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5 text-slate-400" />}
            {isAnalyzing ? 'Analyzing...' : (analyzeResult ? 'Re-Analyze' : 'Analyze')}
          </button>

          <button
            onClick={toggleFavorite}
            className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
              favorites.includes(repoUrl)
                ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                : 'bg-[#161c2e] text-slate-300 border-[#1c2438] hover:text-white'
            }`}
          >
            <Star className={`w-3.5 h-3.5 ${favorites.includes(repoUrl) ? 'fill-amber-400 text-amber-400' : 'fill-none'}`} /> Code repository
          </button>

          <button
            onClick={handleGenerateReadme}
            disabled={isGeneratingReadme}
            className="flex items-center gap-1.5 bg-[#161c2e] hover:bg-[#20283f] text-slate-200 border border-[#1c2438] text-xs font-bold px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
          >
            {isGeneratingReadme ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5 text-sky-400" />}
            Auto-README
          </button>
        </div>
      </header>

      {/* 🚀 Main Frame Workspace */}
      <div className="flex-1 flex overflow-hidden p-3 gap-3">
        
        {/* 🔮 Far Left Vertical Navigation Strip with User Account Button at Bottom */}
        <aside className="w-12 bg-[#0e121f] border border-[#1c2438] rounded-xl flex flex-col items-center py-3 justify-between z-20 flex-shrink-0 shadow-lg">
          <div className="flex flex-col items-center space-y-4">
            <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
              <Cpu className="w-4 h-4" />
            </div>
            
            <nav className="flex flex-col space-y-3.5 text-slate-400">
              <button 
                onClick={() => setActiveSidebarView('files')}
                className={`p-2 rounded-lg transition-all ${activeSidebarView === 'files' ? 'text-sky-400 bg-[#161c2e] shadow-inner' : 'hover:text-white hover:bg-[#161c2e]'}`}
                title="Files Explorer"
              >
                <Folder className="w-4 h-4" />
              </button>
              <button 
                onClick={() => setActiveSidebarView('layers')}
                className={`p-2 rounded-lg transition-all ${activeSidebarView === 'layers' ? 'text-sky-400 bg-[#161c2e] shadow-inner' : 'hover:text-white hover:bg-[#161c2e]'}`}
                title="Architecture Layers"
              >
                <Layers className="w-4 h-4" />
              </button>
              
              <button 
                onClick={() => setActiveSidebarView('favorites')}
                className={`p-2 rounded-lg transition-all ${activeSidebarView === 'favorites' ? 'text-amber-400 bg-[#161c2e] shadow-inner' : 'text-amber-400/80 hover:text-amber-400 hover:bg-[#161c2e]'}`}
                title="Favorite Repositories"
              >
                <Star className={`w-4 h-4 ${activeSidebarView === 'favorites' ? 'fill-amber-400' : 'fill-amber-400/20'}`} />
              </button>

              <button 
                onClick={() => setActiveTab('readme')}
                className="p-2 hover:text-white hover:bg-[#161c2e] rounded-lg transition-all"
                title="Generated README"
              >
                <FileText className="w-4 h-4" />
              </button>
            </nav>
          </div>

          {/* 👤 User Account Profile Button at bottom of Left Strip */}
          <button 
            onClick={() => user.loggedIn ? setShowProfileModal(true) : setShowLoginModal(true)}
            className="w-8 h-8 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center text-xs font-bold shadow-lg border border-indigo-400/30 transition-all hover:scale-105"
            title={user.loggedIn ? user.name : "Sign In / Register"}
          >
            {user.loggedIn ? user.avatar : <User className="w-4 h-4" />}
          </button>
        </aside>

        {/* 📁 Files Explorer Sidebar Panel Card */}
        <div className="w-60 bg-[#111625] border border-[#1c2438] rounded-xl flex flex-col p-3 text-xs font-sans shadow-lg flex-shrink-0">
          <div className="flex items-center justify-between text-slate-100 font-bold tracking-wide pb-2.5 mb-2 border-b border-[#1c2438]">
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              {activeSidebarView === 'files' ? 'Files' : activeSidebarView === 'favorites' ? 'Favorite Repos' : 'Architecture Layers'}
            </span>
          </div>

          {/* Search Bar */}
          <div className="bg-[#161c2e] border border-[#1c2438] rounded-lg px-2.5 py-1.5 flex items-center gap-2 mb-3">
            <Search className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <input 
              type="text"
              value={fileSearch}
              onChange={(e) => setFileSearch(e.target.value)}
              placeholder="Search..."
              className="bg-transparent text-xs text-white focus:outline-none w-full font-mono font-semibold"
            />
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500 hover:text-white cursor-pointer flex-shrink-0" />
            <Plus className="w-3.5 h-3.5 text-slate-500 hover:text-white cursor-pointer flex-shrink-0" />
          </div>

          <div className="flex-1 overflow-y-auto space-y-1 font-mono text-xs font-semibold pr-1">
            {activeSidebarView === 'favorites' ? (
              favorites.length > 0 ? (
                favorites
                  .filter((fav) => fav.toLowerCase().includes(fileSearch.toLowerCase()))
                  .map((fav) => (
                    <div
                      key={fav}
                      onClick={() => setRepoUrl(fav)}
                      className="cursor-pointer text-xs text-slate-300 hover:text-white hover:bg-[#161c2e] px-3 py-2 rounded-lg truncate flex items-center gap-2 border border-transparent hover:border-[#1c2438] transition-all"
                    >
                      <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400 flex-shrink-0" />
                      <span className="truncate">{fav.replace('https://github.com/', '')}</span>
                    </div>
                  ))
              ) : (
                <div className="text-slate-500 text-xs p-3 text-center">Favori repo eklenmedi.</div>
              )
            ) : activeSidebarView === 'files' ? (
              fileList
                .filter((f) => f.toLowerCase().includes(fileSearch.toLowerCase()))
                .map((file, idx) => {
                  const cleanName = file.split('/').pop();
                  const isActiveTab = activeTabFile === file;

                  return (
                    <div
                      key={idx}
                      onClick={() => handleOpenFileTab(file)}
                      title={file}
                      className={`flex items-center gap-2 py-1.5 px-2 rounded-lg cursor-pointer font-semibold transition-all ${
                        isActiveTab 
                          ? 'bg-[#1c2438] text-sky-300 border-l-2 border-sky-400' 
                          : 'text-slate-300 hover:bg-[#161c2e] hover:text-sky-300'
                      }`}
                    >
                      <FileCode className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />
                      <span className="truncate">{cleanName}</span>
                    </div>
                  );
                })
            ) : (
              <div className="space-y-2 p-1 font-sans">
                {(analyzeResult?.graph?.layers || []).map((layer, i) => (
                  <div
                    key={i}
                    onClick={() => toggleNodeExpansion(layer.name)}
                    className="bg-[#161c2e] border border-[#1c2438] hover:border-sky-500/40 p-2.5 rounded-xl cursor-pointer transition-all"
                  >
                    <div className="flex items-center justify-between text-xs font-bold text-white">
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: layer.style?.stroke }}></span>
                        <span className="truncate">{layer.name}</span>
                        <span className="text-slate-500 font-semibold flex-shrink-0">({layer.files.length})</span>
                      </span>
                      {expandedNodes[layer.name] ? <ChevronUp className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />}
                    </div>
                  </div>
                ))}
                {!analyzeResult?.graph && (
                  <div className="text-slate-500 text-xs p-3 text-center font-sans">Analyze a repository to see its layers.</div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 🤖 Code Architect AI Stream Center Panel Card */}
        <div 
          style={{ width: `${leftPanelWidth}%` }} 
          className="bg-[#111625] border border-[#1c2438] rounded-xl flex flex-col relative shadow-lg overflow-hidden min-w-[240px]"
        >
          {/* Header */}
          <div className="px-4 py-3 border-b border-[#1c2438] bg-[#0e121f] flex items-center justify-between h-12 flex-shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-6 h-6 bg-indigo-600/20 text-indigo-400 rounded-full border border-indigo-500/30 flex items-center justify-center flex-shrink-0 shadow-inner">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <div className="truncate min-w-0">
                <h2 className="text-xs font-bold text-white tracking-wide truncate">
                  Code Architect AI <span className="text-[10px] text-slate-500 font-normal font-mono">qwen2.5-coder-1.5b</span>
                </h2>
              </div>
            </div>

            <button
              onClick={() => setShowGuardrailsModal(true)}
              className="text-[10px] font-bold text-slate-300 bg-[#161c2e] hover:bg-[#20283f] px-2.5 py-1 rounded-lg border border-[#1c2438] flex items-center gap-1.5 transition-all flex-shrink-0"
            >
              <ShieldCheck className="w-3 h-3 text-emerald-400" /> Guardrails Active
            </button>
          </div>

          {/* Reasoning Stack */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs pb-24 font-sans font-semibold">
            
            {/* Index status -- reflects what has actually been indexed so far,
                rather than narrating steps that are not really running. */}
            <div className="bg-[#161c2e] border border-[#1c2438] rounded-xl p-3.5 space-y-2">
              <div className="flex items-center justify-between text-slate-100 font-bold">
                <div className="flex items-center gap-2 text-xs">
                  <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded-full">
                    {isAnalyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Clock className="w-3.5 h-3.5" />}
                  </div>
                  Index status
                </div>
              </div>

              {isAnalyzing ? (
                <p className="pl-6 text-sky-400 text-xs font-semibold">Fetching and parsing repository files...</p>
              ) : analyzeResult ? (
                <ul className="space-y-1.5 pl-6 text-slate-300 font-semibold list-disc text-xs">
                  <li>{analyzeResult.file_list?.length || 0} source files indexed</li>
                  <li>{analyzeResult.total_chunks || 0} AST chunks (functions, classes, methods)</li>
                  <li>{analyzeResult.graph?.layers?.length || 0} architecture layers detected</li>
                </ul>
              ) : (
                <p className="pl-6 text-slate-400 text-xs font-semibold">
                  No repository indexed yet. Paste a GitHub URL above and click Analyze.
                </p>
              )}
            </div>

            {/* Starter questions, drawn from real indexed components. Shown only
                before the first question so they never crowd the conversation. */}
            {analyzeResult && chatHistory.length === 0 && suggestions.length > 0 && (
              <div className="space-y-2">
                <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">Try asking</span>
                <div className="flex flex-col gap-1.5">
                  {suggestions.map((question) => (
                    <button
                      key={question}
                      onClick={() => handleAsk(null, question)}
                      className="text-left text-xs font-semibold text-sky-300 bg-[#161c2e] hover:bg-[#1c2438] border border-[#1c2438] hover:border-sky-500/40 rounded-lg px-3 py-2 transition-all"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`flex flex-col animate-in fade-in slide-in-from-bottom-2 duration-300 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                {msg.sender === 'user' ? (
                  <div className="bg-indigo-500/20 border border-indigo-400/40 text-indigo-100 px-3.5 py-2 rounded-xl max-w-[90%] font-bold text-xs shadow">
                    {msg.text}
                  </div>
                ) : (
                  <div className="bg-[#161c2e] border border-[#1c2438] rounded-xl p-4 w-full space-y-3 shadow-lg">
                    {msg.confidence_score !== undefined && (
                      <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
                         Match Confidence: %{msg.confidence_score}
                      </span>
                    )}
                    <div className="prose prose-invert prose-sm max-w-none text-xs leading-relaxed prose-headings:text-white prose-strong:text-white prose-p:text-slate-100 prose-p:font-semibold prose-li:text-slate-100">
                      <MarkdownWithCode content={msg.answer || ''} />
                    </div>
                    {msg.streaming && !msg.answer && (
                      <span className="flex items-center gap-2 text-[11px] text-sky-400 font-semibold">
                        <RefreshCw className="w-3 h-3 animate-spin" /> Reading the retrieved code...
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Bottom Floating Input Box */}
          <div className="absolute bottom-3 left-3 right-3 bg-[#161c2e] border border-[#1c2438] rounded-xl p-2 shadow-2xl z-10 min-w-0 max-w-full">
            <form onSubmit={handleAsk} className="flex items-center gap-1.5 min-w-0 w-full">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a question about the repository..."
                className="flex-1 bg-transparent px-2 py-1 text-xs text-white font-semibold focus:outline-none placeholder-slate-500 min-w-0 truncate"
              />
              
              <button
                type="submit"
                disabled={isAsking}
                className="bg-indigo-600 hover:bg-indigo-500 text-white p-1.5 rounded-lg transition-all disabled:opacity-50 shadow flex-shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>

        {/* ↔️ Panel Resizer Handle */}
        <div 
          onMouseDown={handleMouseDownResizer}
          className="w-1.5 bg-[#1c2438] hover:bg-sky-500 cursor-col-resize flex items-center justify-center transition-colors rounded-full z-10"
          title="Drag to resize panels"
        />

        {/* 🎨 Right panel: architecture diagram, code editor and generated README */}
        <div 
          style={{ width: `${100 - leftPanelWidth}%` }} 
          className="bg-[#111625] border border-[#1c2438] rounded-xl flex flex-col p-3 shadow-lg overflow-hidden relative"
        >
          {/* Top Tab Header Bar */}
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#1c2438] font-bold text-xs h-10 flex-shrink-0">
            <div className="flex items-center gap-6">
              <button
                onClick={() => setActiveTab('diagram')}
                className={`flex items-center gap-2 h-full border-b-2 px-1 transition-all ${
                  activeTab === 'diagram' 
                    ? 'border-sky-500 text-sky-400 font-bold' 
                    : 'border-transparent text-slate-400 hover:text-white'
                }`}
              >
                <Layers className="w-4 h-4" /> Architecture Diagram
              </button>

              <button
                onClick={() => setActiveTab('editor')}
                className={`flex items-center gap-2 h-full border-b-2 px-1 transition-all ${
                  activeTab === 'editor' 
                    ? 'border-sky-500 text-sky-400 font-bold' 
                    : 'border-transparent text-slate-400 hover:text-white'
                }`}
              >
                <Code className="w-4 h-4" /> Code Editor {openTabs.length > 0 && `(${openTabs.length})`}
              </button>

              <button
                onClick={() => setActiveTab('readme')}
                className={`flex items-center gap-2 h-full border-b-2 px-1 transition-all ${
                  activeTab === 'readme' 
                    ? 'border-emerald-500 text-emerald-400 font-bold' 
                    : 'border-transparent text-slate-400 hover:text-white'
                }`}
              >
                <FileText className="w-4 h-4" /> Generated README
              </button>
            </div>

            <div className="flex items-center gap-2 text-slate-400 text-xs font-bold">
              <button onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.15))} className="p-1 hover:bg-[#161c2e] rounded text-slate-300" title="Zoom Out"><ZoomOut className="w-3.5 h-3.5" /></button>
              <span className="font-mono text-sky-400 font-bold">{Math.round(zoomLevel * 100)}%</span>
              <button onClick={() => setZoomLevel((z) => Math.min(2.0, z + 0.15))} className="p-1 hover:bg-[#161c2e] rounded text-slate-300" title="Zoom In"><ZoomIn className="w-3.5 h-3.5" /></button>
              <button onClick={() => setIsMaximized(true)} className="p-1 hover:bg-sky-600 text-white rounded bg-sky-600/20 border border-sky-500/30 ml-1" title="Maximize View"><Maximize2 className="w-3.5 h-3.5" /></button>
            </div>
          </div>

          {/* Diagram canvas plus the layer list beside it */}
          {activeTab === 'diagram' && (
            <div className="flex-1 flex flex-col justify-between overflow-hidden gap-3">
              
              {/* Interactive Control Hint Bar */}
              <div className="bg-[#161c2e] border border-[#1c2438] rounded-lg px-3.5 py-1.5 flex items-center justify-between text-xs text-slate-200 font-mono font-semibold flex-shrink-0">
                <span className="flex items-center gap-2">
                  <Network className="w-3.5 h-3.5 text-sky-400" />
                  <span>Click any node in diagram or sidebar to toggle expanding connections</span>
                </span>
                <button 
                  onClick={() => setExpandedNodes({})}
                  className="px-2 py-0.5 bg-[#111625] hover:bg-[#20283f] rounded border border-[#1c2438] text-[11px] font-bold"
                >
                  Collapse All
                </button>
              </div>

              <div className="flex-1 flex gap-3 overflow-hidden items-stretch relative min-h-[420px]">
                {/* SVG Viewer -- frame stays fixed, only the diagram inside scales with zoom */}
                <div className="flex-1 min-w-0 bg-[#090c15] rounded-xl border border-[#1c2438] overflow-auto shadow-inner cursor-pointer">
                  <div
                    ref={diagramContainerRef}
                    className="w-full min-h-full flex justify-center items-center p-4"
                    style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}
                    dangerouslySetInnerHTML={{ __html: svgContent }}
                  />
                </div>

                {/* Layer list -- clicking a layer expands it in the diagram */}
                <div className="w-44 bg-[#161c2e] border border-[#1c2438] rounded-xl p-3 text-xs space-y-2 font-mono flex-shrink-0 shadow-lg overflow-y-auto max-h-full">
                  <span className="text-slate-200 font-bold uppercase tracking-wider text-[11px] block border-b border-[#1c2438] pb-1.5">Interactive Nodes</span>
                  
                  <div className="space-y-2">
                    {Object.entries(analyzeResult?.node_details || {}).map(([key, nodeItem], i) => (
                      <div 
                        key={i} 
                        onClick={() => toggleNodeExpansion(key)}
                        className={`p-2 rounded-xl border cursor-pointer transition-all ${
                          expandedNodes[key]
                            ? 'bg-indigo-600/20 border-sky-400 text-sky-300 shadow'
                            : 'bg-[#111625] border-[#1c2438] text-slate-200 hover:border-sky-500/40'
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold text-xs">
                          <span className="truncate">{nodeItem.label}</span>
                          {expandedNodes[key] ? <ChevronUp className="w-3.5 h-3.5 text-sky-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />}
                        </div>

                        {/* Expanded Sub-Nodes */}
                        {expandedNodes[key] && (
                          <div className="mt-2 pt-2 border-t border-sky-500/30 space-y-1 text-[11px] font-mono text-slate-100">
                            {nodeItem.children?.map((child, cIdx) => (
                              <div key={cIdx} className="bg-[#090c15] p-1.5 rounded border border-[#1c2438]">
                                <span className="text-emerald-400 font-bold block">{child.name}</span>
                                <span className="text-slate-400 text-[10px] font-medium">{child.type} ({child.lines})</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Referenced Files at bottom of Diagram Panel -- only shown once a question has sources */}
              {referencedFiles.length > 0 && (
              <div className="bg-[#161c2e] border border-[#1c2438] rounded-xl p-3 space-y-1.5 text-xs font-mono shadow flex-shrink-0 max-h-32 overflow-y-auto">
                <span className="text-slate-200 font-bold tracking-wider uppercase block text-[11px]">Referenced Files</span>
                <div className="flex flex-col space-y-1">
                  {referencedFiles.map((f, i) => (
                    <div 
                      key={i} 
                      onClick={() => {
                        handleOpenFileTab(f.file);
                        setActiveTab('editor');
                      }}
                      className="flex items-center gap-2 text-sky-400 hover:underline cursor-pointer font-bold text-xs transition-all"
                    >
                      <CornerDownRight className="w-3.5 h-3.5 text-slate-500" />
                      <span>{f.file}</span>
                      <span className="text-slate-400">:{f.lines}</span>
                      {f.name && <span className="text-slate-300 text-xs font-semibold">({f.name})</span>}
                    </div>
                  ))}
                </div>
              </div>
              )}

            </div>
          )}

          {/* Code Editor Tab */}
          {activeTab === 'editor' && (
            <div className="flex-1 bg-[#090c15] border border-[#1c2438] rounded-xl flex flex-col overflow-hidden shadow-2xl">
              <div className="bg-[#0e121f] border-b border-[#1c2438] flex items-center px-2 overflow-x-auto h-9 space-x-1">
                {openTabs.length === 0 ? (
                  <span className="text-xs text-slate-400 font-mono font-semibold px-3">No open file tabs. Click any file in left File Explorer to inspect code.</span>
                ) : (
                  openTabs.map((tabFile, i) => (
                    <div
                      key={i}
                      onClick={() => setActiveTabFile(tabFile)}
                      className={`flex items-center gap-2 px-3 py-1 text-xs font-mono rounded-t-lg border-t-2 cursor-pointer transition-all ${
                        activeTabFile === tabFile
                          ? 'bg-[#090c15] border-sky-400 text-sky-300 font-bold'
                          : 'border-transparent text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <FileCode className="w-3.5 h-3.5 text-sky-400" />
                      <span>{tabFile.split('/').pop()}</span>
                      <X className="w-3 h-3 hover:text-rose-400" onClick={(e) => handleCloseTab(tabFile, e)} />
                    </div>
                  ))
                )}
              </div>

              {activeTabFile ? (
                <div className="flex-1 flex flex-col overflow-hidden">
                  <div className="px-3 py-1.5 bg-[#161c2e] border-b border-[#1c2438] flex items-center justify-between text-xs font-mono">
                    <span className="text-sky-300 font-bold">{activeTabFile}</span>
                    <button onClick={handleCopyActiveCode} className="text-[11px] font-bold text-slate-200 bg-[#111625] px-2.5 py-0.5 rounded border border-[#1c2438]">
                      {isCopied ? "Copied!" : "Copy Code"}
                    </button>
                  </div>

                  <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed">
                    <CodeHighlighter
                      language={languageFromFilePath(activeTabFile)}
                      style={vscDarkPlus}
                      showLineNumbers
                      customStyle={{ background: 'transparent', fontSize: '12px', margin: 0, padding: 0 }}
                      lineNumberStyle={{ color: '#475569', minWidth: '2.5rem' }}
                    >
                      {fileContents[activeTabFile] || "Loading code..."}
                    </CodeHighlighter>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-400 text-xs font-mono font-semibold">
                  Select a file from sidebar to open in Editor.
                </div>
              )}
            </div>
          )}

          {activeTab === 'readme' && (
            <div className="flex-1 bg-[#090c15] p-5 rounded-xl border border-[#1c2438] overflow-y-auto shadow-lg">
              {!readmeMarkdown && isGeneratingReadme ? (
                <div className="flex items-center gap-2.5 text-xs text-sky-400 font-semibold">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Writing README from the indexed code... this takes a couple of minutes on a local model.
                </div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none prose-headings:text-white prose-strong:text-white prose-code:text-sky-300 prose-a:text-sky-400">
                  <ReactMarkdown>{readmeMarkdown || 'No README generated yet. Click "Auto-README" in header.'}</ReactMarkdown>
                </div>
              )}
            </div>
          )}

        </div>

      </div>

      {/* 🔐 Login Modal */}
      {showLoginModal && (
        <div onClick={() => setShowLoginModal(false)} className="fixed inset-0 bg-[#08090f]/95 backdrop-blur-xl z-50 flex items-center justify-center p-6">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-[#111625] border border-[#1c2438] rounded-2xl shadow-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-[#1c2438] pb-3">
              <h2 className="text-sm font-bold text-white">Sign In to Codetrace AI</h2>
              <X className="w-4 h-4 text-slate-400 cursor-pointer" onClick={() => setShowLoginModal(false)} />
            </div>
            <form onSubmit={handleLoginSubmit} className="space-y-3">
              {authMode === 'register' && (
                <input type="text" value={authName} onChange={(e) => setAuthName(e.target.value)} placeholder="Your name" className="w-full bg-[#161c2e] border border-[#1c2438] rounded-lg px-3 py-2 text-xs text-white" />
              )}
              <input type="email" required value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} placeholder="architect@codetrace.ai" className="w-full bg-[#161c2e] border border-[#1c2438] rounded-lg px-3 py-2 text-xs text-white" />
              <input type="password" required value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} placeholder="••••••••••••" className="w-full bg-[#161c2e] border border-[#1c2438] rounded-lg px-3 py-2 text-xs text-white" />
              {authError && <p className="text-rose-400 text-xs">{authError}</p>}
              <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2 rounded-lg text-xs">
                {authMode === 'register' ? 'Create Account' : 'Sign In'}
              </button>
              <p className="text-xs text-slate-400 text-center">
                {authMode === 'register' ? 'Already have an account? ' : "Don't have an account? "}
                <span
                  className="text-indigo-400 cursor-pointer"
                  onClick={() => { setAuthMode(authMode === 'register' ? 'login' : 'register'); setAuthError(''); }}
                >
                  {authMode === 'register' ? 'Sign In' : 'Register'}
                </span>
              </p>
            </form>
          </div>
        </div>
      )}

      {/* 👤 Profile Modal */}
      {showProfileModal && (
        <div onClick={() => setShowProfileModal(false)} className="fixed inset-0 bg-[#08090f]/90 backdrop-blur-md z-50 flex items-center justify-center p-6">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-[#111625] border border-[#1c2438] rounded-2xl shadow-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-[#1c2438] pb-3">
              <h3 className="text-sm font-bold text-white">{user.name}</h3>
              <X className="w-4 h-4 text-slate-400 cursor-pointer" onClick={() => setShowProfileModal(false)} />
            </div>
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-200">⭐ Bookmarked Repositories</span>
              {savedRepos.map((repo, i) => (
                <div key={i} className="p-2 bg-[#161c2e] rounded-lg text-xs font-mono text-sky-300">{repo}</div>
              ))}
              <button
                onClick={handleToggleFavoriteRepo}
                disabled={!repoUrl}
                className="w-full flex items-center justify-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border border-[#1c2438] bg-[#161c2e] hover:bg-[#20283f] text-slate-200 disabled:opacity-40 transition-all"
              >
                {savedRepos.includes(repoUrl)
                  ? <><BookmarkCheck className="w-3.5 h-3.5 text-emerald-400" /> Remove Current Repo</>
                  : <><Bookmark className="w-3.5 h-3.5" /> Bookmark Current Repo</>}
              </button>
            </div>
            <button onClick={handleLogout} className="px-3 py-1 bg-rose-600/20 text-rose-400 rounded-lg text-xs font-bold border border-rose-500/30">Sign Out</button>
          </div>
        </div>
      )}

      {/* 🔍 Guardrails Modal */}
      {showGuardrailsModal && (
        <div onClick={() => setShowGuardrailsModal(false)} className="fixed inset-0 bg-[#08090f]/90 backdrop-blur-md z-50 flex items-center justify-center p-6">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-[#111625] border border-[#1c2438] rounded-2xl shadow-2xl p-6 space-y-3">
            <div className="flex justify-between items-center border-b border-[#1c2438] pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" /> Guardrails Active
              </h3>
              <X className="w-4 h-4 text-slate-400 cursor-pointer" onClick={() => setShowGuardrailsModal(false)} />
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-semibold">
              Codetrace AI answers only from code it has actually indexed. Before the
              model is called, a question is checked against the indexed vocabulary:
              if its distinctive terms never appear in the code, the question is
              refused outright rather than answered from the model's own memory.
              Every answer carries the file and line numbers it was drawn from.
            </p>
          </div>
        </div>
      )}

      {/* 🔎 Maximized Diagram Overlay */}
      {isMaximized && (
        <div className="fixed inset-0 bg-[#090c15] z-50 flex flex-col p-4">
          <div className="flex items-center justify-between mb-3 flex-shrink-0">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" /> Architecture Diagram
            </span>
            <button
              onClick={() => setIsMaximized(false)}
              className="p-1.5 hover:bg-[#161c2e] rounded-lg text-slate-300 border border-[#1c2438]"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {/* diagram-fit scales the SVG down to fit the screen (see index.css),
              so the fullscreen view never needs scrolling. */}
          <div
            className="diagram-fit flex-1 min-h-0 overflow-hidden flex justify-center items-center bg-[#111625] border border-[#1c2438] rounded-xl p-4"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}

    </div>
  );
}

export default App;
