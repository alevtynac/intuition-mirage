# Intuition Mirage

An interactive art and poetry experience where intuition guides image selection, creating a personalized collage and AI-generated poetry.

## Concept

**Intuition Mirage** is a surreal, meditative experience that explores the relationship between intuition, choice, and artistic expression. Players make 15 intuitive selections from images paired with poetic prompts, building a "Memory Collage" that reflects their subconscious choices. The game then transforms these selections into AI-generated poetry, creating a unique artistic reflection of the player's intuitive journey.

### Core Philosophy

- **Logic is powerless here**: The game encourages players to trust their intuition over rational analysis
- **Surreal prompts**: Each selection is guided by poetic, abstract phrases like "Blue rain", "Time smells like rust", or "Flying trees"
- **Automatic art generation**: Player choices automatically form a visual collage and inspire AI poetry
- **Reflection and revelation**: The experience culminates in a revelation screen that contemplates the nature of intuition itself

## Features

### Interactive Experience
- **Welcome Screen**: Typewriter-style introduction explaining the concept
- **Intuitive Selection**: Choose between 2 images at a time based on surreal prompts
- **15 Selections**: Build your intuition collage through 15 meaningful choices
- **Audio Atmosphere**: Ambient background music and click sound effects with mute control

### Visual Art Generation
- **Memory Collage**: Automatically arranged 3×5 grid collage of all selected images
- **Intuition Poetry Visualization**: Surreal collage composition with 4 selected images overlaid on a gradient background
- **Selection History Ticker**: Continuous scrolling feed showing all selections with their prompts at the bottom

### AI Poetry Generation
- **Automatic Poetry**: Backend generates 15-19 line poems from selected image prompts
- **Poetic Constraints**: 
  - Includes 4 image prompts verbatim (exactly once each)
  - Contains at least 3 sensory details (sound, smell, touch, taste, sight)
  - Features exactly one question mark
  - No prompts in the title/first line
- **Surreal Composition**: Poetry combines prompts with abstract, dreamlike imagery

### Revelation Screen
- **Contemplative Ending**: Final screen reflecting on the nature of intuition
- **Repeatable Experience**: Option to restart and explore different intuitive paths

## Installation

1. Open VS Code or another IDE (VS Code is recommended option)
2. Add working folder by cloning GitHub repository using this link:<br>
`https://github.com/alevtynac/intuition-mirage`
3. Install Python dependencies by running the command below in Terminal Window into VS Code:
```bash
pip install -r requirements.txt
```

2. Ensure you have PNG images in the `images/` directory (numbered 1.png through 80.png)

3. Ensure audio files are in the `audio/` directory:
   - `ambience.mpeg` - Background ambient sound
   - `mouse-click.mpeg` - Click sound effect

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Wait for the welcome screen text to finish typing, then press → or click to begin

## How to Play

1. **Welcome Screen**: Read the introduction (typewriter effect)
2. **Start**: Press the right arrow key (→) or click anywhere once text is complete
3. **Selection Phase**: 
   - Two images appear with a surreal prompt at the bottom
   - Click the image that resonates with the prompt
   - Make 15 total selections
   - Each selection excludes the other image from future rounds
4. **Completion**: After 15 selections, view your Memory Collage and Intuition Poetry
5. **Revelation**: Click "To learn more" to see the revelation screen
6. **Repeat**: Press → to experience a new intuitive journey

## Game Mechanics

### Selection System
- **Photo Pool**: Dynamically loaded PNG images from the `images/` directory
- **Random Positioning**: Images appear at random positions with random sizes (80-180px)
- **Non-overlapping**: Algorithm ensures images don't overlap
- **Exclusion**: Selected images and their pairs are excluded from future selections
- **Prompt System**: Each pair of images is associated with a unique poetic prompt

### Collage Generation
- **Memory Collage**: 3 columns × 5 rows grid layout
- **Preserved Sizes**: Images maintain their selection size in the collage
- **No Rotation**: Images remain straight (0° rotation)
- **Positioned Left**: Collage appears on the left side of the screen

### Poetry Generation
- **4 Random Images**: System randomly selects 4 images from your 15 choices
- **Prompt Combination**: Combines the prompts from those 4 images
- **Markov-style Generation**: Creates surreal poetry following specific constraints
- **Visual Display**: Poetry appears next to the Intuition Poetry visualization

### Intuition Poetry Visualization
- **Gradient Background**: Random pastel gradient (20+ color palette variations)
- **4 Image Overlay**: Selected images arranged with varied sizes, rotations, and opacity
- **Surreal Composition**: Dynamic positioning creates a dreamlike collage effect

## Technical Details

### Architecture
- **Backend**: Flask (Python) with in-memory game state storage
- **Frontend**: HTML5 Canvas with vanilla JavaScript
- **Responsive**: Scales to different screen sizes while maintaining aspect ratio
- **Retina Support**: High-DPI display support

### Image System
- **Format**: PNG files only
- **Dynamic Loading**: Images loaded on-demand and cached
- **Dimension Caching**: Image dimensions cached for performance
- **Aspect Ratio Preservation**: Images maintain original aspect ratios

### Audio System
- **Ambient Loop**: Background music loops continuously
- **Click Feedback**: Sound effect on interactions
- **Mute Control**: Toggle audio with button in top-right corner
- **Autoplay Handling**: Gracefully handles browser autoplay restrictions

### Animation System
- **Typewriter Effect**: Character-by-character text reveal
- **Progress Bar**: Animated generation progress for poetry visualization
- **Scrolling Ticker**: Continuous horizontal scroll for selection history
- **Smooth Transitions**: RequestAnimationFrame-based animation loop

## Project Structure

```
intuition-mirage/
├── app.py                 # Flask backend with game logic and poetry generation
├── templates/
│   └── index.html        # Frontend HTML/JavaScript/Canvas rendering
├── images/               # PNG image files (1.png, 2.png, etc.)
├── audio/                # Audio files (ambience.mpeg, mouse-click.mpeg)
├── requirements.txt      # Python dependencies
├── LICENSE               # License file
└── README.md             # This file
```

## API Endpoints

- `GET /` - Main game page
- `GET /images/<filename>` - Serve PNG images
- `GET /audio/<filename>` - Serve audio files
- `POST /api/game/new` - Create a new game session
- `GET /api/game/<game_id>/state` - Get current game state
- `POST /api/game/<game_id>/start` - Start the game
- `POST /api/game/<game_id>/select` - Handle image selection
- `GET /api/game/<game_id>/collage` - Get Memory Collage data
- `GET /api/game/<game_id>/intuition-world` - Get Intuition Poetry data (images, prompts, poem)
- `GET /api/photos` - Get list of available photos
- `GET /api/photos/<filename>/dimensions` - Get image dimensions

## Poetic Prompts

The game includes 15 surreal prompts that guide selections:
- "Blue rain"
- "Time smells like rust"
- "Flying trees"
- "Gravity is a lie"
- "Glass clouds in the sky"
- "Your shadow is dancing"
- "Paper wind blows"
- "Metal starts to breathe"
- "Dark fire"
- "Silence is very loud"
- "Liquid gold"
- "Flowers made of bone"
- "The Old Future is Here"
- "City Built on Clouds"
- "Very Cold Light"

## Poetry Generation Algorithm

The poetry generator follows strict constraints:
1. **Length**: 15-19 lines
2. **Prompt Inclusion**: Each of 4 selected prompts appears verbatim exactly once
3. **Sensory Details**: At least 3 different sensory types (sound, smell, touch, taste, sight)
4. **Question Mark**: Exactly one question mark in the entire poem
5. **Title Rule**: No prompts in the first line (title)
6. **Uniqueness**: No duplicate lines, minimal word overlap between lines

## Notes

- **Game State**: Stored in memory (use Redis or database for production/multi-user)
- **Session IDs**: Each game gets a unique 4-digit ID
- **Concurrent Games**: Supports multiple simultaneous sessions
- **Image Requirements**: PNG format required, any dimensions supported
- **Browser Compatibility**: Modern browsers with Canvas and ES6 support

## Version

**Build 2.0.0** - Current version as of this documentation

## License

See LICENSE file for details.
