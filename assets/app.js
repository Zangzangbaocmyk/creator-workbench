/* ============================================
   创作者工作台 - 共享工具库
   数据存储 · 通用工具 · 页面逻辑
   ============================================ */

// ====== 数据存储层 (localStorage) ======
const Store = {
  // 通用读取
  get(key, defaultValue = null) {
    const raw = localStorage.getItem(`cw_${key}`);
    if (!raw) return defaultValue;
    try { return JSON.parse(raw); } catch { return defaultValue; }
  },

  // 通用写入
  set(key, value) {
    localStorage.setItem(`cw_${key}`, JSON.stringify(value));
  },

  // 通用删除
  remove(key) {
    localStorage.removeItem(`cw_${key}`);
  },

  // ====== 任务管理 ======
  getTasks() {
    return this.get('tasks', []);
  },
  saveTasks(tasks) {
    this.set('tasks', tasks);
  },
  addTask(task) {
    const tasks = this.getTasks();
    task.id = Date.now().toString();
    task.createdAt = new Date().toISOString();
    task.done = false;
    tasks.unshift(task);
    this.saveTasks(tasks);
    return task;
  },
  toggleTask(id) {
    const tasks = this.getTasks();
    const t = tasks.find(x => x.id === id);
    if (t) { t.done = !t.done; this.saveTasks(tasks); }
  },
  deleteTask(id) {
    const tasks = this.getTasks().filter(x => x.id !== id);
    this.saveTasks(tasks);
  },

  // ====== 视频管理 ======
  getVideos() {
    return this.get('videos', []);
  },
  saveVideos(videos) {
    this.set('videos', videos);
  },
  addVideo(video) {
    const videos = this.getVideos();
    video.id = Date.now().toString();
    video.addedAt = new Date().toISOString();
    videos.unshift(video);
    this.saveVideos(videos);
    return video;
  },
  deleteVideo(id) {
    const videos = this.getVideos().filter(x => x.id !== id);
    this.saveVideos(videos);
  },
  updateVideo(id, updates) {
    const videos = this.getVideos();
    const v = videos.find(x => x.id === id);
    if (v) { Object.assign(v, updates); this.saveVideos(videos); }
  },

  // ====== 复盘管理 ======
  getReviews() {
    return this.get('reviews', []);
  },
  addReview(review) {
    const reviews = this.getReviews();
    review.id = Date.now().toString();
    review.createdAt = new Date().toISOString();
    reviews.unshift(review);
    this.set('reviews', reviews);
    return review;
  },
  deleteReview(id) {
    const reviews = this.getReviews().filter(x => x.id !== id);
    this.set('reviews', reviews);
  },

  // ====== 灵感管理 ======
  getInspirations() {
    return this.get('inspirations', []);
  },
  addInspiration(insp) {
    const list = this.getInspirations();
    insp.id = Date.now().toString();
    insp.createdAt = new Date().toISOString();
    list.unshift(insp);
    this.set('inspirations', list);
    return insp;
  },
  deleteInspiration(id) {
    const list = this.getInspirations().filter(x => x.id !== id);
    this.set('inspirations', list);
  },
  toggleInspirationUsed(id) {
    const list = this.getInspirations();
    const i = list.find(x => x.id === id);
    if (i) { i.used = !i.used; this.set('inspirations', list); }
  },

  // ====== 统计 ======
  getStats() {
    const tasks = this.getTasks();
    const videos = this.getVideos();
    const reviews = this.getReviews();
    const inspirations = this.getInspirations();
    const today = new Date().toDateString();
    const todayTasks = tasks.filter(t => 
      new Date(t.createdAt).toDateString() === today
    );
    return {
      totalTasks: tasks.length,
      todayTasks: todayTasks.length,
      doneTasks: todayTasks.filter(t => t.done).length,
      totalVideos: videos.length,
      totalReviews: reviews.length,
      totalInspirations: inspirations.length,
      unusedInspirations: inspirations.filter(i => !i.used).length,
    };
  }
};

// ====== 工具函数 ======
const Utils = {
  // 格式化数字
  formatNumber(n) {
    if (n >= 100000) return (n / 10000).toFixed(1) + '万';
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
  },

  // 格式化日期
  formatDate(dateStr) {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  },

  // 格式化日期时间
  formatDateTime(dateStr) {
    const d = new Date(dateStr);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  },

  // 相对时间
  timeAgo(dateStr) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / 86400000);
    if (days > 0) return `${days}天前`;
    const hours = Math.floor(diff / 3600000);
    if (hours > 0) return `${hours}小时前`;
    const mins = Math.floor(diff / 60000);
    if (mins > 0) return `${mins}分钟前`;
    return '刚刚';
  },

  // 提示
  toast(msg, type = 'success') {
    let el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.className = `toast show ${type}`;
    clearTimeout(el._timer);
    el._timer = setTimeout(() => {
      el.className = `toast ${type}`;
    }, 2500);
  },

  // 转义HTML
  escape(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  },

  // 获取今天日期字符串
  today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  },

  // 获取星期
  weekDay() {
    const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return days[new Date().getDay()];
  }
};

// ====== 侧边栏生成 ======
function renderSidebar(activePage) {
  const pages = [
    { key: 'index', href: 'index.html', icon: '📋', label: '今日任务' },
    { key: 'trending', href: 'trending.html', icon: '🔥', label: '热门视频' },
    { key: 'review', href: 'review.html', icon: '📊', label: '内容复盘' },
    { key: 'inspiration', href: 'inspiration.html', icon: '💡', label: '灵感库' },
  ];

  const stats = Store.getStats();
  
  return `
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-logo">
        <span>🎬</span> 创作者工作台
      </div>
      <div class="sidebar-section">导航</div>
      <nav class="sidebar-nav">
        ${pages.map(p => `
          <a href="${p.href}" class="nav-item ${p.key === activePage ? 'active' : ''}">
            <span class="icon">${p.icon}</span>
            <span>${p.label}</span>
          </a>
        `).join('')}
      </nav>
      <div class="sidebar-section">概览</div>
      <div style="padding: 0 24px;">
        <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:var(--text-secondary);">
          <span>今日任务</span>
          <span style="color:var(--accent);font-weight:600;">${stats.doneTasks}/${stats.todayTasks}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:var(--text-secondary);">
          <span>收藏视频</span>
          <span style="color:var(--info);font-weight:600;">${stats.totalVideos}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:var(--text-secondary);">
          <span>复盘记录</span>
          <span style="color:var(--purple);font-weight:600;">${stats.totalReviews}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:var(--text-secondary);">
          <span>灵感待用</span>
          <span style="color:var(--warning);font-weight:600;">${stats.unusedInspirations}</span>
        </div>
      </div>
      <div class="sidebar-section" style="margin-top:20px;">${Utils.today()} · ${Utils.weekDay()}</div>
    </aside>
  `;
}

// ====== 初始化页面框架 ======
function initPage(activePage, pageTitle, subtitle) {
  document.body.innerHTML = `
    <div class="app-layout">
      ${renderSidebar(activePage)}
      <main class="main-content">
        <div class="page-header">
          <div>
            <h1 class="page-title">${pageTitle}</h1>
            <p class="page-subtitle">${subtitle}</p>
          </div>
          <div id="page-actions"></div>
        </div>
        <div id="page-content"></div>
      </main>
    </div>
  `;
}
