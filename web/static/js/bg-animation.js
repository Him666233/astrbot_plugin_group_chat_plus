/**
 * Background particle network animation
 * Pure client-side, theme-aware, performance-optimized
 */
(function() {
    'use strict';

    var canvas = document.getElementById('bg-canvas');
    if (!canvas) return;

    var ctx = canvas.getContext('2d');

    // --- Configuration (adaptive) ---
    function getConfig() {
        var w = window.innerWidth;
        if (w < 768) {
            return { particleCount: 28, connectDist: 100, speed: 0.2 };
        } else if (w < 1024) {
            return { particleCount: 45, connectDist: 130, speed: 0.28 };
        } else {
            return { particleCount: 65, connectDist: 155, speed: 0.32 };
        }
    }

    var config = getConfig();
    var particles = [];
    var animId = null;
    var isDark = true;

    // --- Theme helpers ---
    function readTheme() {
        return document.documentElement.getAttribute('data-theme') !== 'light';
    }

    function colorRGB() {
        // Softer in light theme
        return isDark ? { r: 224, g: 32, b: 32 } : { r: 170, g: 38, b: 38 };
    }

    // --- Canvas sizing ---
    function resize() {
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = window.innerWidth * dpr;
        canvas.height = window.innerHeight * dpr;
        canvas.style.width = window.innerWidth + 'px';
        canvas.style.height = window.innerHeight + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // --- Particles ---
    function createParticles() {
        var w = window.innerWidth;
        var h = window.innerHeight;
        particles = [];
        for (var i = 0; i < config.particleCount; i++) {
            particles.push({
                x: Math.random() * w,
                y: Math.random() * h,
                vx: (Math.random() - 0.5) * config.speed * 2,
                vy: (Math.random() - 0.5) * config.speed * 2,
                size: Math.random() * 2 + 0.8,
                phase: Math.random() * Math.PI * 2,
                phaseStep: 0.004 + Math.random() * 0.018,
            });
        }
    }

    function updateParticles() {
        var w = window.innerWidth;
        var h = window.innerHeight;
        var margin = 60;
        for (var i = 0; i < particles.length; i++) {
            var p = particles[i];
            p.x += p.vx;
            p.y += p.vy;
            p.phase += p.phaseStep;

            if (p.x < -margin) p.x = w + margin;
            if (p.x > w + margin) p.x = -margin;
            if (p.y < -margin) p.y = h + margin;
            if (p.y > h + margin) p.y = -margin;
        }
    }

    function draw() {
        var w = window.innerWidth;
        var h = window.innerHeight;
        var rgb = colorRGB();
        var r = rgb.r, g = rgb.g, b = rgb.b;
        var maxDist = config.connectDist;
        var maxDistSq = maxDist * maxDist;
        var lineAlpha = isDark ? 0.06 : 0.04;
        var coreAlpha = isDark ? 0.45 : 0.25;
        var glowAlpha = isDark ? 0.16 : 0.08;

        ctx.clearRect(0, 0, w, h);

        // Draw connection lines between nearby particles
        for (var i = 0; i < particles.length; i++) {
            for (var j = i + 1; j < particles.length; j++) {
                var dx = particles[i].x - particles[j].x;
                var dy = particles[i].y - particles[j].y;
                var distSq = dx * dx + dy * dy;
                if (distSq < maxDistSq) {
                    var dist = Math.sqrt(distSq);
                    var alpha = (1 - dist / maxDist) * lineAlpha;
                    ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + alpha.toFixed(4) + ')';
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw particles with glow
        for (var k = 0; k < particles.length; k++) {
            var p = particles[k];
            var pulse = p.size + Math.sin(p.phase) * 0.5;

            // Outer glow
            var grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, pulse * 3.5);
            grad.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + glowAlpha.toFixed(3) + ')');
            grad.addColorStop(0.45, 'rgba(' + r + ',' + g + ',' + b + ',' + (glowAlpha * 0.35).toFixed(4) + ')');
            grad.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(p.x, p.y, pulse * 3.5, 0, Math.PI * 2);
            ctx.fill();

            // Bright core
            ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + coreAlpha.toFixed(3) + ')';
            ctx.beginPath();
            ctx.arc(p.x, p.y, pulse, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // --- Loop ---
    function loop() {
        updateParticles();
        draw();
        animId = requestAnimationFrame(loop);
    }

    function start() {
        resize();
        config = getConfig();
        createParticles();
        if (animId) cancelAnimationFrame(animId);
        loop();
    }

    function stop() {
        if (animId) {
            cancelAnimationFrame(animId);
            animId = null;
        }
    }

    // --- Events ---

    // Pause when tab hidden
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) stop();
        else start();
    });

    // Watch theme changes
    new MutationObserver(function(mutations) {
        for (var i = 0; i < mutations.length; i++) {
            if (mutations[i].attributeName === 'data-theme') {
                isDark = readTheme();
            }
        }
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    // Debounced resize
    var resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            stop();
            start();
        }, 250);
    });

    // --- Init ---
    isDark = readTheme();
    start();
})();
