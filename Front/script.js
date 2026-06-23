const views = document.querySelectorAll('.view');
const navItems = document.querySelectorAll('.nav-item[data-view]');
const breadcrumbCurrent = document.getElementById('breadcrumbCurrent');
const sidebar = document.getElementById('sidebar');
const mobileOverlay = document.getElementById('mobileOverlay');

function switchView(viewId) {
  const target = document.getElementById(viewId);
  if (!target) return;

  views.forEach((view) => view.classList.toggle('active', view === target));
  navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === viewId));
  breadcrumbCurrent.textContent = target.dataset.title;
  sidebar.classList.remove('open');
  mobileOverlay.classList.remove('show');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navItems.forEach((item) => item.addEventListener('click', () => switchView(item.dataset.view)));
document.querySelectorAll('[data-view-link]').forEach((item) => item.addEventListener('click', () => switchView(item.dataset.viewLink)));

document.getElementById('menuButton').addEventListener('click', () => {
  sidebar.classList.toggle('open');
  mobileOverlay.classList.toggle('show');
});
mobileOverlay.addEventListener('click', () => {
  sidebar.classList.remove('open');
  mobileOverlay.classList.remove('show');
});

const modals = document.querySelectorAll('.modal-backdrop');
const uploadModal = document.getElementById('uploadModal');
const progressModal = document.getElementById('progressModal');
const reportModal = document.getElementById('reportModal');
const helpModal = document.getElementById('helpModal');

function openModal(modal) {
  modals.forEach((item) => item.classList.remove('open'));
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModals() {
  modals.forEach((modal) => modal.classList.remove('open'));
  document.body.style.overflow = '';
}

document.querySelectorAll('[data-open-upload]').forEach((button) => button.addEventListener('click', () => openModal(uploadModal)));
document.querySelectorAll('[data-close-modal]').forEach((button) => button.addEventListener('click', closeModals));
modals.forEach((modal) => modal.addEventListener('click', (event) => {
  if (event.target === modal && modal !== progressModal) closeModals();
}));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !progressModal.classList.contains('open')) closeModals();
});

const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const modalDropZone = document.getElementById('modalDropZone');

function showSelectedFile(file) {
  if (!file) return;
  const size = (file.size / 1024 / 1024).toFixed(1).replace('.', ',');
  fileName.textContent = `${file.name} · ${size} МБ`;
}

fileInput.addEventListener('change', () => showSelectedFile(fileInput.files[0]));
['dragenter', 'dragover'].forEach((eventName) => modalDropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  modalDropZone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach((eventName) => modalDropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  modalDropZone.classList.remove('dragover');
}));
modalDropZone.addEventListener('drop', (event) => showSelectedFile(event.dataTransfer.files[0]));

document.getElementById('uploadForm').addEventListener('submit', (event) => {
  event.preventDefault();
  openModal(progressModal);
  runCheckAnimation();
});

function runCheckAnimation() {
  const bar = document.getElementById('scanProgress');
  const percent = document.getElementById('scanPercent');
  const text = document.getElementById('progressText');
  let value = 0;
  bar.style.width = '0%';
  percent.textContent = '0%';

  const timer = setInterval(() => {
    value += Math.floor(Math.random() * 8) + 4;
    if (value >= 100) value = 100;
    if (value > 35) text.textContent = 'Нормализуем идентификаторы и сравниваем AST…';
    if (value > 70) text.textContent = 'Ищем похожие решения и формируем отчёт…';
    bar.style.width = `${value}%`;
    percent.textContent = `${value}%`;
    if (value === 100) {
      clearInterval(timer);
      setTimeout(() => showReport(88, 'Лабораторная работа №5'), 500);
    }
  }, 140);
}

function showReport(score, title = 'Лабораторная работа №4') {
  document.getElementById('reportTitle').textContent = title;
  document.getElementById('reportScore').textContent = `${score}%`;
  document.getElementById('reportRing').style.setProperty('--progress', score);
  document.getElementById('originalMetric').textContent = `${score}%`;
  document.getElementById('matchMetric').textContent = `${100 - score}%`;
  document.getElementById('sourceMetric').textContent = score < 70 ? '8' : score < 85 ? '5' : '3';

  const alert = document.getElementById('reportAlert');
  if (score < 70) {
    alert.classList.add('is-warning');
    alert.querySelector('span').textContent = '!';
    alert.querySelector('strong').textContent = 'Работа требует доработки';
    alert.querySelector('p').textContent = 'Оригинальность ниже рекомендуемого порога 70%.';
  } else {
    alert.classList.remove('is-warning');
    alert.querySelector('span').textContent = '✓';
    alert.querySelector('strong').textContent = 'Работа прошла проверку';
    alert.querySelector('p').textContent = 'Уровень оригинальности соответствует требованиям дисциплины.';
  }
  openModal(reportModal);
}

document.querySelectorAll('[data-report]').forEach((button) => button.addEventListener('click', () => showReport(Number(button.dataset.report))));

const searchInput = document.getElementById('submissionSearch');
const statusFilter = document.getElementById('statusFilter');
const submissionCards = document.querySelectorAll('.submission-card');
const emptyState = document.getElementById('emptyState');

function filterSubmissions() {
  const query = searchInput.value.toLowerCase().trim();
  const status = statusFilter.value;
  let visibleCount = 0;
  submissionCards.forEach((card) => {
    const matchesQuery = card.dataset.search.includes(query);
    const matchesStatus = status === 'all' || card.dataset.status === status;
    const isVisible = matchesQuery && matchesStatus;
    card.style.display = isVisible ? 'grid' : 'none';
    if (isVisible) visibleCount += 1;
  });
  emptyState.style.display = visibleCount ? 'none' : 'block';
}

searchInput.addEventListener('input', filterSubmissions);
statusFilter.addEventListener('change', filterSubmissions);

document.getElementById('helpButton').addEventListener('click', () => openModal(helpModal));
document.getElementById('knowledgeHelpButton').addEventListener('click', () => openModal(helpModal));

const toast = document.getElementById('toast');
document.getElementById('downloadReport').addEventListener('click', () => {
  const title = document.getElementById('reportTitle').textContent;
  const score = document.getElementById('reportScore').textContent;
  const report = [
    'ЛАБКОНТРОЛЬ — ОТЧЁТ О ПРОВЕРКЕ',
    '',
    `Работа: ${title}`,
    `Оригинальность: ${score}`,
    `Структурное сходство: ${document.getElementById('matchMetric').textContent}`,
    `Найдено похожих решений: ${document.getElementById('sourceMetric').textContent}`,
    '',
    'Результат сформирован демонстрационной версией системы.'
  ].join('\n');
  const url = URL.createObjectURL(new Blob([report], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'labcontrol-report.txt';
  link.click();
  URL.revokeObjectURL(url);
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2600);
});
