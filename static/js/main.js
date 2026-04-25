// Global Javascript file for overall site interactivity (non-Alpine)
document.addEventListener('DOMContentLoaded', () => {
    // Hide flash messages slowly after 5 seconds
    setTimeout(() => {
        const flashes = document.querySelectorAll('.animate-fade-in-up');
        flashes.forEach(flash => {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                flash.style.display = 'none';
            }, 300);
        });
    }, 5000);
});
