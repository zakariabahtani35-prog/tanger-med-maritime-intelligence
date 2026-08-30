/**
 * Morocco Maritime & Port Intelligence - Landing Page Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. FAQ Accordion Toggle
    const accordionItems = document.querySelectorAll('.accordion-item');
    accordionItems.forEach(item => {
        const trigger = item.querySelector('.accordion-trigger');
        trigger.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            
            // Close other accordion items for clean single-item view
            accordionItems.forEach(otherItem => {
                otherItem.classList.remove('active');
                const otherTrigger = otherItem.querySelector('.accordion-trigger');
                if (otherTrigger) {
                    otherTrigger.setAttribute('aria-expanded', 'false');
                }
            });

            // Toggle current item
            if (!isActive) {
                item.classList.add('active');
                trigger.setAttribute('aria-expanded', 'true');
            }
        });
    });

    // Automatically open first FAQ by default
    if (accordionItems.length > 0) {
        accordionItems[0].classList.add('active');
        const firstTrigger = accordionItems[0].querySelector('.accordion-trigger');
        if (firstTrigger) {
            firstTrigger.setAttribute('aria-expanded', 'true');
        }
    }

    // 2. Mobile Menu Toggle
    const mobileBtn = document.getElementById('mobile-toggle-btn');
    const navMenu = document.getElementById('nav-menu');
    if (mobileBtn && navMenu) {
        mobileBtn.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            const icon = mobileBtn.querySelector('i');
            if (icon) {
                if (navMenu.classList.contains('active')) {
                    icon.className = 'ri-close-line';
                } else {
                    icon.className = 'ri-menu-4-line';
                }
            }
        });

        // Close menu on link click
        navMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navMenu.classList.remove('active');
                const icon = mobileBtn.querySelector('i');
                if (icon) {
                    icon.className = 'ri-menu-4-line';
                }
            });
        });
    }

    // 3. Header Scroll Shadow, Elevation & Active Link Highlight (Scrollspy)
    const navCapsule = document.getElementById('nav-capsule');
    const headerElement = document.querySelector('header');
    const navLinks = document.querySelectorAll('.nav-links-menu .nav-item-link');
    const sections = document.querySelectorAll('section[id]');

    function onScroll() {
        if (navCapsule) {
            if (window.scrollY > 30) {
                navCapsule.style.boxShadow = '0 12px 35px rgba(1, 1, 1, 0.14), 0 2px 6px rgba(1, 1, 1, 0.06)';
                navCapsule.style.background = 'rgba(255, 255, 255, 0.98)';
            } else {
                navCapsule.style.boxShadow = '0 8px 30px rgba(1, 1, 1, 0.08), 0 1px 3px rgba(1, 1, 1, 0.04)';
                navCapsule.style.background = 'rgba(255, 255, 255, 0.95)';
            }
        }

        // Scrollspy active state detection
        let currentSectionId = '';
        const scrollPosition = window.scrollY + 130;

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                currentSectionId = section.getAttribute('id');
            }
        });

        if (currentSectionId) {
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === `#${currentSectionId}`) {
                    link.classList.add('active');
                }
            });
        }
    }

    window.addEventListener('scroll', onScroll);
    onScroll();

    // 4. Smooth Anchor Scrolling with header offset
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            if (targetId && targetId !== '#') {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    e.preventDefault();
                    const headerHeight = headerElement ? headerElement.offsetHeight + 20 : 90;
                    const elementPosition = targetElement.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - headerHeight;

                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
});

// 5. Newsletter Submission Handler
function handleNewsletter() {
    const emailInput = document.getElementById('newsletter-email');
    const successMsg = document.getElementById('newsletter-success');
    const form = document.getElementById('newsletter-form');

    if (emailInput && emailInput.value) {
        if (successMsg) {
            successMsg.style.display = 'block';
        }
        if (form) {
            form.style.display = 'none';
        }
    }
}
