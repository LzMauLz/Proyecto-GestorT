document.addEventListener('DOMContentLoaded', () => {
  const shelf = document.querySelector('[data-store-shelf]');
  if (!shelf) return;
  const track = shelf.querySelector('[data-store-carousel]');
  const controls = shelf.querySelector('[data-carousel-controls]');
  const previous = shelf.querySelector('[data-carousel-prev]');
  const next = shelf.querySelector('[data-carousel-next]');
  const toggle = shelf.querySelector('[data-carousel-toggle]');
  const cards = [...track.querySelectorAll('[data-shelf-card]')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = false;
  let timer;

  const status = shelf.querySelector('[data-carousel-status]');
  function reportPosition() {
    if (!shelf.matches(':hover, :focus-within') && !paused) return;
    const start = cards[0].offsetLeft;
    const first = cards.find(card => card.offsetLeft - start + card.offsetWidth > track.scrollLeft + 2);
    if (first) status.textContent = first.querySelector('h3').textContent;
  }

  function move(direction) {
    const positions = cards.map(card => card.offsetLeft - cards[0].offsetLeft);
    const last = track.scrollWidth - track.clientWidth;
    let target;
    if (direction > 0) {
      target = track.scrollLeft >= last - 2 ? 0 : positions.find(left => left > track.scrollLeft + 2) ?? last;
    } else {
      target = track.scrollLeft < 2 ? last : positions.reverse().find(left => left < track.scrollLeft - 2) ?? 0;
    }
    track.scrollTo({left: target, behavior: motion.matches ? 'auto' : 'smooth'});
  }

  function schedule() {
    clearTimeout(timer);
    if (paused || controls.hidden || motion.matches || document.hidden || shelf.matches(':hover, :focus-within')) return;
    timer = setTimeout(() => {
      move(1);
      schedule();
    }, 20_000);
  }

  function updateControls() {
    controls.hidden = cards.length < 2 || track.scrollWidth <= track.clientWidth + 2;
    toggle.hidden = motion.matches;
    schedule();
  }

  track.addEventListener('scrollend', reportPosition);
  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  toggle.addEventListener('click', () => {
    paused = !paused;
    toggle.textContent = paused ? 'Reanudar' : 'Pausar';
    schedule();
  });
  for (const event of ['mouseenter', 'mouseleave', 'focusin', 'focusout']) {
    shelf.addEventListener(event, () => queueMicrotask(schedule));
  }
  motion.addEventListener('change', updateControls);
  window.addEventListener('resize', updateControls);
  document.addEventListener('visibilitychange', schedule);
  track.dataset.carouselReady = '';
  updateControls();
});
