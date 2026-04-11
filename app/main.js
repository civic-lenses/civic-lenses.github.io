// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
  });
});

// Mobile topic chip switching
document.querySelectorAll('.mobile-topic').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.mobile-topic').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
  });
});

// Mobile bottom nav switching
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
  });
});

// Sidebar nav switching
document.querySelectorAll('.sidebar-nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const section = item.closest('.sidebar-section');
    if (!section) return;
    section.querySelectorAll('.sidebar-nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
  });
});
