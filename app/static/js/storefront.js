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
  let category = '';
  const normalized = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim().replace(/\s+/g, ' ');
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
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
      shelf.hidden = !shelfCards.some(card => !card.hidden);
      track.scrollLeft = 0;
      requestAnimationFrame(updateArrows);
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
  if (track) {
    previous.addEventListener('click', () => track.scrollBy({left: -track.clientWidth * .85, behavior: reducedMotion() ? 'auto' : 'smooth'}));
    next.addEventListener('click', () => track.scrollBy({left: track.clientWidth * .85, behavior: reducedMotion() ? 'auto' : 'smooth'}));
    track.addEventListener('scroll', updateArrows, {passive: true});
    window.addEventListener('resize', updateArrows);
  }
  filter();
});
