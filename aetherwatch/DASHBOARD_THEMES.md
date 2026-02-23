# AetherWatch Dashboard Themes

All 10 artistic dashboard variants have been created and are accessible via simple numeric routes.

## Available Themes

### Default - Comic Book Style
- **URL**: [http://localhost:5001/](http://localhost:5001/)
- **Style**: Original comic book themed dashboard
- **Colors**: Vibrant primary colors with Ben-Day dot textures
- **Features**: POW! BAM! exclamations, comic panel borders

### Theme 1 - Cyberpunk Neon
- **URL**: [http://localhost:5001/1](http://localhost:5001/1)
- **Style**: Magenta and cyan neon lights
- **Colors**: #FF00FF (magenta), #00FFFF (cyan)
- **Font**: Orbitron
- **Features**: Scanline animations, neon glow effects, grid overlay

### Theme 2 - Tactical Terminal
- **URL**: [http://localhost:5001/2](http://localhost:5001/2)
- **Style**: Military green terminal interface
- **Colors**: #00FF00 (green) on black
- **Font**: Share Tech Mono
- **Features**: Radar pulse animations, clipped polygon borders, monospace

### Theme 3 - Retro CRT
- **URL**: [http://localhost:5001/3](http://localhost:5001/3)
- **Style**: Amber CRT terminal from the 1980s
- **Colors**: #FFB000 (amber) on black
- **Font**: VT323 (vintage terminal)
- **Features**: Screen flicker effect, CRT scanlines, terminal blink animation

### Theme 4 - Minimalist Swiss
- **URL**: [http://localhost:5001/4](http://localhost:5001/4)
- **Style**: Black/white/red Swiss design
- **Colors**: High contrast with red accents
- **Font**: Helvetica
- **Features**: Grid-based layout, 4px borders, 2px gaps, hover transitions

### Theme 5 - Brutalist Architecture
- **URL**: [http://localhost:5001/5](http://localhost:5001/5)
- **Style**: Dark concrete brutalist architecture
- **Colors**: Dark gray (#111), white text
- **Font**: Space Grotesk (weight 700)
- **Features**: Bold 5em headers, heavy 5px borders, inset shadows, scale transforms

### Theme 6 - Glassmorphism
- **URL**: [http://localhost:5001/6](http://localhost:5001/6)
- **Style**: Purple gradient with glass blur effects
- **Colors**: Purple gradient (#667eea → #764ba2 → #f093fb)
- **Font**: Poppins
- **Features**: backdrop-filter blur(10px), rounded borders, translucent cards

### Theme 7 - Matrix Digital Rain
- **URL**: [http://localhost:5001/7](http://localhost:5001/7)
- **Style**: Green Matrix movie terminal
- **Colors**: #00FF00 (Matrix green) on black
- **Font**: Courier Prime
- **Features**: Falling characters animation, flickering, text-shadow glow

### Theme 8 - Victorian Steampunk
- **URL**: [http://localhost:5001/8](http://localhost:5001/8)
- **Style**: Bronze and copper Victorian steampunk
- **Colors**: #D4A574 (bronze), #B47828 (copper)
- **Font**: Cinzel (serif)
- **Features**: Gear spin animations, ornate borders, Victorian ornaments

### Theme 9 - Holographic Futuristic
- **URL**: [http://localhost:5001/9](http://localhost:5001/9)
- **Style**: Cyan/magenta holographic interface
- **Colors**: #00FFFF (cyan), #FF00FF (magenta) gradients
- **Font**: Exo 2
- **Features**: Hue rotation animation, float effects, gradient borders, pulse

### Theme 10 - Material Design Dark
- **URL**: [http://localhost:5001/10](http://localhost:5001/10)
- **Style**: Google Material Design dark theme
- **Colors**: #BB86FC (purple), #03DAC6 (teal) on #121212 background
- **Font**: Roboto (300, 500, 700 weights)
- **Features**: Elevation shadows, 3px top accent bars, cubic-bezier transitions

## Quick Access

All dashboards share the same JavaScript functionality (`/static/dashboard.js`) and display identical data - only the visual styling differs.

```bash
# Start the application
docker-compose up -d

# Access any theme
open http://localhost:5001/     # Original comic book
open http://localhost:5001/1    # Cyberpunk
open http://localhost:5001/2    # Tactical
open http://localhost:5001/3    # Retro CRT
open http://localhost:5001/4    # Minimalist
open http://localhost:5001/5    # Brutalist
open http://localhost:5001/6    # Glassmorphism
open http://localhost:5001/7    # Matrix
open http://localhost:5001/8    # Steampunk
open http://localhost:5001/9    # Holographic
open http://localhost:5001/10   # Material Design
```

## Technical Details

- **Shared JavaScript**: All dashboards use `/static/dashboard.js` for functionality
- **Code Reuse**: ~180 lines of JavaScript extracted into shared file
- **Consistent Data**: All themes display identical fleet status, drone data, and traces
- **Live Updates**: 2-second polling for real-time data
- **Responsive**: Grid-based layouts adapt to different screen sizes

## Design Inspiration

The themes draw from diverse artistic and design movements:
- **Digital**: Cyberpunk, Matrix, Holographic
- **Military**: Tactical Terminal
- **Historical**: Retro CRT (1980s), Steampunk (Victorian)
- **Design Movements**: Swiss Minimalism, Brutalism, Material Design
- **Modern**: Glassmorphism

Each theme is fully functional and production-ready with complete CSS animations and hover effects.
