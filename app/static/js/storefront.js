document.addEventListener('DOMContentLoaded', () => {
  const catalog = document.querySelector('[data-store-catalog]');
  if (!catalog) return;
  const searchForm = document.querySelector('[data-store-search]');
  const search = searchForm?.querySelector('input[name="q"]');
  const cards = [...catalog.querySelectorAll('[data-product-card]')];
  const chips = [...catalog.querySelectorAll('[data-category-filter]')];
  const status = catalog.querySelector('[data-results-status]');
  const empty = catalog.querySelector('[data-no-results]');
  const shelf = document.querySelector('[data-store-shelf]');
  const track = document.querySelector('[data-store-carousel]');
  const controls = document.querySelector('[data-carousel-controls]');
  const previous = document.querySelector('[data-carousel-prev]');
  const next = document.querySelector('[data-carousel-next]');
  const toggle = document.querySelector('[data-carousel-toggle]');
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  let category = '';
  let paused = false;
  let autoAdvance;
  const normalized = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim().replace(/\s+/g, ' ');
  const reducedMotion = () => motionPreference.matches;
  const updateArrows = () => {
    if (!track || !controls) return;
    const overflow = track.scrollWidth > track.clientWidth + 2;
    controls.hidden = !overflow;
    previous.disabled = track.scrollLeft < 2;
    next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
  };
  const filter = () => {
    const terms = normalized(search?.value).split(' ').filter(Boolean);
    const matches = card => (!category || normalized(card.dataset.category) === category)
      && terms.every(term => normalized(card.dataset.search).includes(term));
    cards.forEach(card => { card.hidden = !matches(card); });
    const count = cards.filter(card => !card.hidden).length;
    status.textContent = `${count} ${count === 1 ? 'producto' : 'productos'} ${terms.length || category ? 'que coinciden con tu búsqueda' : 'publicados'}`;
    empty.hidden = count > 0;
    if (track && shelf) {
      const shelfCards = [...track.querySelectorAll('[data-shelf-card]')];
      shelfCards.forEach(card => { card.hidden = !matches(card); });
      const visibleCount = shelfCards.filter(card => !card.hidden).length;
      track.dataset.count = visibleCount;
      shelf.hidden = visibleCount === 0;
      track.scrollLeft = 0;
      requestAnimationFrame(() => {
        updateArrows();
        scheduleAdvance();
      });
    }
  };
  catalog.querySelector('[data-category-tools]').hidden = false;
  chips.forEach(chip => chip.addEventListener('click', () => {
    category = normalized(chip.dataset.categoryFilter);
    chips.forEach(item => item.setAttribute('aria-pressed', String(item === chip)));
    filter();
  }));
  search?.addEventListener('input', filter);
  searchForm?.addEventListener('submit', event => {
    event.preventDefault();
    filter();
    catalog.scrollIntoView({behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start'});
  });
  catalog.querySelector('[data-clear-search]').addEventListener('click', () => {
    if (search) search.value = '';
    category = '';
    chips.forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.categoryFilter === '')));
    filter();
    search?.focus();
  });
  const canAdvance = () => track && !controls.hidden && !shelf.hidden && !paused && !reducedMotion()
    && !document.hidden && !shelf.matches(':hover, :focus-within');
  const scheduleAdvance = () => {
    clearTimeout(autoAdvance);
    if (!canAdvance()) return;
    autoAdvance = setTimeout(() => {
      if (!canAdvance()) return;
      if (next.disabled) {
        track.scrollTo({left: 0, behavior: 'smooth'});
        scheduleAdvance();
      } else {
        next.click();
      }
    }, 20_000);
  };
  if (track) {
    const scroll = direction => {
      const cards = [...track.querySelectorAll('[data-shelf-card]:not([hidden])')];
      const start = cards[0]?.offsetLeft ?? 0;
      const positions = cards.map(card => card.offsetLeft - start);
      const left = direction > 0 ? positions.find(position => position > track.scrollLeft + 6)
        : positions.reverse().find(position => position < track.scrollLeft - 6);
      track.scrollTo({left: left ?? (direction > 0 ? track.scrollWidth : 0), behavior: reducedMotion() ? 'auto' : 'smooth'});
      scheduleAdvance();
    };
    previous.addEventListener('click', () => scroll(-1));
    next.addEventListener('click', () => scroll(1));
    toggle.addEventListener('click', () => {
      paused = !paused;
      toggle.textContent = paused ? 'Reanudar' : 'Pausar';
      scheduleAdvance();
    });
    const syncMotion = () => {
      toggle.hidden = reducedMotion();
      scheduleAdvance();
    };
    motionPreference.addEventListener('change', syncMotion);
    toggle.hidden = reducedMotion();
    track.dataset.carouselReady = '';
    track.addEventListener('scroll', updateArrows, {passive: true});
    window.addEventListener('resize', () => {
      updateArrows();
      scheduleAdvance();
    });
    document.addEventListener('visibilitychange', scheduleAdvance);
    ['mouseenter', 'mouseleave', 'focusin', 'focusout'].forEach(event => {
      shelf.addEventListener(event, () => queueMicrotask(scheduleAdvance));
    });
  }
  filter();
});
