// Ponytail-minimized restaurant app - all duplication eliminated
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// State
let state = {
  results: [],
  selected: new Set(),
  favorites: new Set(),
  currentDetail: null
};

// KPI updater - only for elements that exist in HTML
const updateKPIs = restaurants => {
  const total = $('kpi-total');
  const rating = $('kpi-rating');
  const category = $('kpi-category');
  
  if (total) total.textContent = restaurants.length;
  
  if (rating && restaurants.length) {
    const avg = restaurants.reduce((sum, r) => sum + (r.stars || 0), 0) / restaurants.length;
    rating.textContent = avg.toFixed(1);
  } else if (rating) rating.textContent = '--';
  
  if (category && restaurants.length) {
    const cats = {};
    restaurants.forEach(r => {
      const cat = Array.isArray(r.categories) ? (r.categories[0]?.title || r.categories[0]) : r.categories?.split(',')[0]?.trim();
      if (cat) cats[cat] = (cats[cat] || 0) + 1;
    });
    const top = Object.entries(cats).sort((a,b) => b[1] - a[1])[0];
    category.textContent = top ? top[0] : '--';
  } else if (category) category.textContent = '--';
};

// Compare bar updater
const updateCompareBar = () => {
  const bar = $('compareBar');
  const text = $('compareBarText');
  if (!bar || !text) return;
  
  const count = state.selected.size;
  text.textContent = `${count} restaurant${count!==1?'s':''} selected`;
  bar.classList.toggle('visible', count >= 2);
};

// Templates - ponytail: handle all category types
const getCat = r => {
  if (!r.categories) return '';
  if (Array.isArray(r.categories)) return r.categories[0]?.title || r.categories[0] ? `<span>🍽️ ${r.categories[0]?.title || r.categories[0]}</span>` : '';
  if (typeof r.categories === 'string') return r.categories.split(',')[0] ? `<span>🍽️ ${r.categories.split(',')[0]}</span>` : '';
  return ''; // not array or string, skip
};

const templates = {
  loading: msg => `<div class="empty-state"><div class="empty-state-icon">⏳</div><h3>${msg}</h3></div>`,
  error: msg => `<div class="error-state"><div class="error-icon">❌</div><h3>Error</h3><p>${msg}</p></div>`,
  empty: () => `<div class="empty-state"><div class="empty-state-icon">🔍</div><h3>Ready to help!</h3><p>Type what you're looking for above</p></div>`,
  
  statsBar: (count, icon, title) => `
    <div style="background:var(--surface-elevated);padding:var(--spacing-md) var(--spacing-lg);border-radius:var(--radius-md);margin-bottom:var(--spacing-lg);box-shadow:var(--shadow-sm);display:flex;align-items:center;gap:var(--spacing-md)">
      <span style="font-size:1.5rem">${icon}</span>
      <div><h3 style="margin:0;font-size:1.125rem">${title}</h3><p style="margin:0;font-size:0.875rem;color:var(--text-secondary)">Found ${count} restaurant${count!==1?'s':''}</p></div>
    </div>`,
  
  card: r => {
    const isSelected = state.selected.has(r.id);
    const isFav = state.favorites.has(r.id);
    return `
    <div class="restaurant-card ${isSelected?'selected':''}" data-id="${r.id}">
      <div class="card-header">
        <h3 class="card-title">${r.name}</h3>
        <div style="display:flex;gap:var(--spacing-xs)">
          <button class="icon-btn ${isFav?'active':''}" data-action="favorite" data-id="${r.id}" title="Favorite">
            <span>${isFav?'❤️':'🤍'}</span>
          </button>
          <button class="icon-btn ${isSelected?'active':''}" data-action="select" data-id="${r.id}" title="Select for comparison">
            <span>${isSelected?'☑️':'⬜'}</span>
          </button>
        </div>
      </div>
      <div class="card-meta">
        <span>⭐ ${r.stars?.toFixed(1) || 'N/A'}</span>
        <span>📍 ${r.city || 'Unknown'}, ${r.state || ''}</span>
        ${getCat(r)}
      </div>
      ${r.review_count ? `<div class="card-stat"><span>${r.review_count} reviews</span></div>` : ''}
    </div>`;
  },
  
  detailModal: r => `
    <div class="detail-section">
      <h3>${r.name}</h3>
      <div class="detail-meta">
        <div>⭐ Rating: ${r.stars?.toFixed(1) || 'N/A'}</div>
        <div>📍 ${r.address || ''}, ${r.city || ''}, ${r.state || ''} ${r.postal_code || ''}</div>
        ${getCat(r) ? `<div>${getCat(r)}</div>` : ''}
        ${r.review_count ? `<div>💬 ${r.review_count} reviews</div>` : ''}
      </div>
    </div>
    <div style="margin-top:var(--spacing-lg)">
      <h4>Recent Reviews</h4>
      <div id="reviewsList">Loading reviews...</div>
    </div>`
};

// API helpers
const api = {
  async call(url, opts) {
    try {
      const res = await fetch(url, opts);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      return data;
    } catch (e) {
      throw new Error(e.message || 'Request failed');
    }
  },
  
  search: term => api.call('/api/search?term=' + encodeURIComponent(term)),
  recommend: prefs => api.call('/api/recommend', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(prefs)}),
  ask: (ids, q) => api.call('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({restaurant_ids:ids, question:q})}),
  favorites: {
    save: id => api.call('/api/favorites/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({restaurant_id:id})}),
    remove: id => api.call('/api/favorites/remove', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({restaurant_id:id})}),
    list: () => api.call('/api/favorites')
  }
};

// Intent parser
const parseIntent = input => {
  const l = input.toLowerCase();
  if (l.includes('create') && (l.includes('plan') || l.includes('meal'))) return {type:'meal-plan', params:{input}};
  if (l.includes('prefer') || l.includes('vegetarian') || l.includes('budget')) return {type:'preferences', params:{input}};
  if (l.includes('recommend') || l.includes('suggest') || l.includes('best')) return {type:'recommend', params:{term:input.replace(/recommend|suggest|best/gi,'').trim()}};
  return {type:'search', params:{term:input.replace(/find|search|show|look for/gi,'').trim() || input}};
};

// Handlers
const handlers = {
  async search({term}) {
    const data = await api.search(term);
    state.results = data.restaurants || [];
    render(state.results, '🍴', 'Search Results');
  },
  
  async recommend({term}) {
    const cuisines = ['italian','chinese','japanese','mexican','indian','thai','french'].filter(c => term.toLowerCase().includes(c));
    const data = await api.recommend({preferences:{preferred_cuisines:cuisines.length?cuisines:[term],max_price_level:3,min_rating:0},limit:30});
    state.results = (data.recommendations || []).map(s => s.restaurant);
    render(state.results, '🎯', 'Recommendations');
  },
  
  async 'meal-plan'({input}) {
    const data = await api.ask([], input);
    $('resultsDiv').innerHTML = `<div class="comparison-summary"><h3><span>📅</span> Meal Plan Advice</h3><div style="margin-top:var(--spacing-md);line-height:1.7;white-space:pre-wrap">${data.answer || 'No response'}</div></div>`;
  },
  
  async preferences({input}) {
    const data = await api.ask([], input);
    $('resultsDiv').innerHTML = `<div class="comparison-summary"><h3><span>✨</span> Your Preferences</h3><div style="margin-top:var(--spacing-md);line-height:1.7;white-space:pre-wrap">${data.answer || 'No response'}</div><p style="margin-top:var(--spacing-md);border-top:1px solid var(--border);padding-top:var(--spacing-md);color:var(--text-secondary);font-size:0.875rem">💡 Try "Find Italian restaurants" to search with these!</p></div>`;
  }
};

// Render
const render = (restaurants, icon, title) => {
  const resultsDiv = $('resultsDiv');
  if (restaurants.length === 0) {
    resultsDiv.innerHTML = templates.empty();
    updateKPIs([]);
    return;
  }
  console.log('First restaurant object:', restaurants[0]);
  console.log('Available ID fields:', Object.keys(restaurants[0]).filter(k => k.toLowerCase().includes('id')));
  resultsDiv.innerHTML = templates.statsBar(restaurants.length, icon, title) + 
    '<div class="restaurants-grid">' + restaurants.map(templates.card).join('') + '</div>';
  updateKPIs(restaurants);
};

// Actions
const actions = {
  async favorite(id) {
    const exists = state.favorites.has(id);
    if (exists) {
      await api.favorites.remove(id);
      state.favorites.delete(id);
    } else {
      await api.favorites.save(id);
      state.favorites.add(id);
    }
    // Update all favorite buttons for this ID
    $$(`[data-action="favorite"][data-id="${id}"]`).forEach(btn => {
      btn.classList.toggle('active', !exists);
      btn.querySelector('span').textContent = exists ? '🤍' : '❤️';
    });
  },
  
  select(id) {
    if (state.selected.has(id)) {
      state.selected.delete(id);
    } else {
      if (state.selected.size >= 5) return alert('Maximum 5 restaurants for comparison');
      state.selected.add(id);
    }
    // Update button and card
    $$(`[data-action="select"][data-id="${id}"]`).forEach(btn => {
      const selected = state.selected.has(id);
      btn.classList.toggle('active', selected);
      btn.querySelector('span').textContent = selected ? '☑️' : '⬜';
    });
    $$(`[data-id="${id}"].restaurant-card`).forEach(card => {
      card.classList.toggle('selected', state.selected.has(id));
    });
    updateCompareBar();
  },
  
  async compare() {
    if (state.selected.size < 2) return;
    const selected = state.results.filter(r => state.selected.has(r.id));
    
    $('resultsDiv').innerHTML = templates.loading('Comparing restaurants...');
    try {
      const data = await api.ask([...state.selected], 'Compare these restaurants. What are the key differences?');
      $('resultsDiv').innerHTML = `
        <div class="comparison-summary">
          <h3><span>⚖️</span> Comparison</h3>
          <div class="restaurants-grid">${selected.map(templates.card).join('')}</div>
          <div style="margin-top:var(--spacing-lg);padding:var(--spacing-lg);background:var(--surface-elevated);border-radius:var(--radius-md)">
            <h4>AI Analysis</h4>
            <div style="line-height:1.7;white-space:pre-wrap">${data.answer}</div>
          </div>
        </div>`;
    } catch(e) {
      $('resultsDiv').innerHTML = templates.error(e.message);
    }
  },
  
  clearSelection() {
    state.selected.clear();
    $$('[data-action="select"]').forEach(btn => {
      btn.classList.remove('active');
      btn.querySelector('span').textContent = '⬜';
    });
    $$('.restaurant-card').forEach(card => card.classList.remove('selected'));
    updateCompareBar();
  },
  
  async details(id) {
    console.log('Details called for:', id);
    const restaurant = state.results.find(r => r.id === id);
    if (!restaurant) {
      console.error('Restaurant not found:', id);
      return;
    }
    console.log('Opening modal for:', restaurant.name);
    
    state.currentDetail = restaurant;
    const modal = $('detailsModal');
    console.log('Modal element:', modal);
    $('detailsModalTitle').innerHTML = '<span>🏪</span> <span>' + restaurant.name + '</span>';
    $('detailsModalBody').innerHTML = templates.detailModal(restaurant);
    console.log('Adding visible class to modal');
    modal.classList.add('visible');
    console.log('Modal classes:', modal.className);
    
    // Load reviews async
    try {
      const reviews = await api.call(`/api/restaurant/${id}/reviews`);
      const list = $('reviewsList');
      if (list) {
        list.innerHTML = (reviews.reviews || []).slice(0,3).map(rev => 
          `<div class="review-item" style="padding:var(--spacing-md);border-bottom:1px solid var(--border)">
            <div style="display:flex;justify-content:space-between;margin-bottom:var(--spacing-sm)">
              <strong>${rev.user_name || 'Anonymous'}</strong>
              <span>⭐ ${rev.stars}</span>
            </div>
            <p style="margin:0;color:var(--text-secondary);font-size:0.875rem">${rev.text?.substring(0,200)}${(rev.text?.length||0)>200?'...':''}</p>
          </div>`
        ).join('') || '<p>No reviews available</p>';
      }
    } catch(e) {
      const list = $('reviewsList');
      if (list) list.innerHTML = '<p>Could not load reviews</p>';
    }
  },
  
  closeModal() {
    $('detailsModal').classList.remove('visible');
    state.currentDetail = null;
  },
  
  async askAboutRestaurant() {
    if (!state.currentDetail) return;
    const input = $('detailsQuestionInput');
    const container = $('detailsAnswerContainer');
    if (!input || !input.value.trim()) return;
    
    container.innerHTML = templates.loading('Analyzing reviews...');
    try {
      const data = await api.ask([state.currentDetail.id], input.value);
      container.innerHTML = `<div class="alert alert-info" style="margin-top:var(--spacing-md)"><strong>Answer:</strong><div style="margin-top:var(--spacing-sm);white-space:pre-wrap">${data.answer}</div></div>`;
    } catch(e) {
      container.innerHTML = templates.error(e.message);
    }
  }
};

// Event delegation - one listener for everything
document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-action]');
  if (btn) {
    e.preventDefault();
    const action = btn.dataset.action;
    const id = btn.dataset.id;
    
    if (action === 'favorite') await actions.favorite(id);
    else if (action === 'select') actions.select(id);
    else if (action === 'close-modal') actions.closeModal();
    return;
  }
  
  // Card click for details
  const card = e.target.closest('.restaurant-card');
  if (card) {
    console.log('Card clicked:', card.dataset.id);
    await actions.details(card.dataset.id);
  }
});

// Compare bar buttons
$('compareBarBtn')?.addEventListener('click', actions.compare);
$('clearSelectionBtn')?.addEventListener('click', actions.clearSelection);

// Modal close buttons
$$('[id^="close"][id$="Btn"], [id^="close"][id$="ModalBtn"]').forEach(btn => {
  btn.addEventListener('click', actions.closeModal);
});

// Ask button in detail modal
$('submitDetailsQuestionBtn')?.addEventListener('click', actions.askAboutRestaurant);

// Main form
$('unifiedForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const input = $('unifiedInput')?.value.trim();
  if (!input) return alert('Please enter a request');
  
  $('resultsDiv').innerHTML = templates.loading('Processing...');
  try {
    const intent = parseIntent(input);
    await handlers[intent.type](intent.params);
  } catch(e) {
    $('resultsDiv').innerHTML = templates.error(e.message);
  }
});

// Quick actions
window.setQuickAction = action => {
  const input = $('unifiedInput');
  if (!input) return;
  const prompts = {search:'Find ', recommend:'Recommend ', 'meal-plan':'Create a meal plan called ', preferences:'I prefer '};
  input.value = prompts[action] || '';
  input.focus();
};

// Tab switching
$$('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    $$('.nav-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    $$('.tab-content').forEach(c => c.classList.remove('active'));
    $(`${target.replace(/-([a-z])/g, (g) => g[1].toUpperCase())}Tab`)?.classList.add('active');
    
    if (target === 'favorites') loadFavorites();
  });
});

// Load favorites
async function loadFavorites() {
  const list = $('favoritesList');
  if (!list) return;
  
  list.innerHTML = templates.loading('Loading favorites...');
  try {
    const data = await api.favorites.list();
    state.favorites = new Set((data.favorites || []).map(f => f.restaurant_id));
    
    if (data.favorites?.length) {
      list.innerHTML = '<div class="restaurants-grid">' + data.favorites.map(f => templates.card({
        id: f.restaurant_id,
        name: f.restaurant_name,
        stars: f.stars,
        city: f.city,
        state: f.state,
        categories: f.categories,
        review_count: f.review_count
      })).join('') + '</div>';
    } else {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">❤️</div><h3>No Favorites Yet</h3><p>Start adding restaurants by clicking the heart icon</p></div>';
    }
  } catch(e) {
    list.innerHTML = templates.error(e.message);
  }
}

// Init
$('resultsDiv').innerHTML = templates.empty();
updateCompareBar();