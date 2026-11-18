document.addEventListener('DOMContentLoaded', () => {
  const feedback = document.querySelector('#form-feedback');
  if (feedback?.querySelector('.flash.error')) feedback.focus();
  document.querySelector('[data-tracking-feedback]')?.focus();
});
