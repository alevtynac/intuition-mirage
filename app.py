from flask import Flask, render_template, jsonify, request, send_from_directory
import random
import math
import os
import re
from pathlib import Path
from PIL import Image as PILImage

app = Flask(__name__)

# Game state storage (in production, use Redis or database)
game_states = {}

# Image directory
IMAGES_DIR = Path(__file__).parent / 'images'
# Audio directory
AUDIO_DIR = Path(__file__).parent / 'audio'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Cache for image dimensions (PNG files)
image_dimensions_cache = {}

def get_image_dimensions(filename):
    """Get dimensions of a PNG/image file"""
    if filename in image_dimensions_cache:
        return image_dimensions_cache[filename]
    
    image_path = IMAGES_DIR / filename
    if not image_path.exists():
        return None
    
    try:
        with PILImage.open(image_path) as img:
            dimensions = {
                'width': img.width,
                'height': img.height,
                'format': img.format
            }
            image_dimensions_cache[filename] = dimensions
            return dimensions
    except Exception as e:
        print(f"Error reading image dimensions for {filename}: {e}")
        return None

def get_photo_pool():
    """Scan images directory and return list of image filenames (PNG files)"""
    if not IMAGES_DIR.exists():
        IMAGES_DIR.mkdir(exist_ok=True)
        # Return empty list if no images directory exists yet
        return []
    
    # Get all PNG image files from the images directory
    image_files = []
    for file in IMAGES_DIR.iterdir():
        if file.is_file() and file.suffix.lower() == '.png':
            image_files.append(file.name)
            # Pre-load dimensions for PNG files
            get_image_dimensions(file.name)
    
    # If no images found, return empty list (frontend will handle fallback)
    return sorted(image_files)

# Photo pool - dynamically loaded from images directory (PNG files only)
PHOTO_POOL = get_photo_pool()

# Poetic prompts for the game (surreal statements)
POETIC_PROMPTS = [
    "Blue rain",
    "Time smells like rust",
    "Flying trees",
    "Gravity is a lie",
    "Glass clouds in the sky",
    "Your shadow is dancing",
    "Paper wind blows",
    "Metal starts to breathe",
    "Dark fire",
    "Silence is very loud",
    "Liquid gold",
    "Flowers made of bone",
    "The Old Future is Here",
    "City Built on Clouds",
    "Very Cold Light"
]


class PhotoOption:
    """Represents a photo option with position and size"""
    def __init__(self, photo_id, x, y, size=None):
        self.photo_id = photo_id
        self.x = x
        self.y = y
        # Random size between 80 and 180 pixels
        self.size = size if size is not None else random.uniform(80, 180)
    
    def to_dict(self):
        return {
            'photo_id': self.photo_id,
            'x': self.x,
            'y': self.y,
            'size': self.size
        }


class GameState:
    """Manages game state for photo selection game"""
    def __init__(self, game_id, width=1820, height=750):
        self.game_id = game_id
        self.width = width
        self.height = height
        self.human_steps = 15
        self.game_complete = False
        self.game_started = False
        
        # Track chosen photos (only selected photos, for collage)
        self.human_chosen_photos = []
        
        # Track chosen prompts with photos (for display)
        self.human_chosen_prompts = []  # List of dicts: {'photo_id': str, 'prompt': str}
        
        # Track excluded photos (shown but not selected, excluded from future selections)
        self.human_excluded_photos = []
        
        # Current photo options displayed
        self.human_current_options = []  # List of PhotoOption objects
        
        # Current prompt displayed with options
        self.current_prompt = None
        
        # Track used prompts to ensure each appears only once
        self.used_prompts = []
        
        # Initialize first options
        self._generate_human_options()
    
    def _get_random_position(self):
        """Generate random position for a photo option"""
        top_margin = 100
        bottom_margin = self.height - 80
        side_margin = 60
        
        x = random.uniform(side_margin, self.width - side_margin)
        y = random.uniform(top_margin, bottom_margin)
        return x, y
    
    def _get_two_non_overlapping_positions(self):
        """Generate two positions that don't overlap and stay within screen boundaries"""
        # Estimate max image size at 1/2 scale (accounting for large images)
        # Assuming max original size around 600px, 1/2 would be ~300px
        max_estimated_size = 300  # Maximum 1/2 size dimension estimate
        min_distance = max_estimated_size + 100  # Minimum distance between photos (size + padding)
        
        # Margins to prevent border overflow - account for 1/2 size images
        # Leave space at top for counter and at bottom for prompt text
        top_margin = 120 + max_estimated_size // 2  # Space for counter
        bottom_margin = self.height - 150 - max_estimated_size // 2  # Space for prompt text
        side_margin = 60 + max_estimated_size // 2
        
        max_attempts = 200
        for _ in range(max_attempts):
            x1 = random.uniform(side_margin, self.width - side_margin)
            x2 = random.uniform(side_margin, self.width - side_margin)
            
            y1 = random.uniform(top_margin, bottom_margin)
            y2 = random.uniform(top_margin, bottom_margin)
            
            # Check if positions are far enough apart to prevent overlap
            distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            if distance >= min_distance:
                # Verify both positions are within boundaries
                if (side_margin <= x1 <= self.width - side_margin and
                    side_margin <= x2 <= self.width - side_margin and
                    top_margin <= y1 <= bottom_margin and
                    top_margin <= y2 <= bottom_margin):
                    return [(x1, y1), (x2, y2)]
        
        # Fallback: place them on opposite corners with safe margins
        x1 = side_margin
        x2 = self.width - side_margin
        y1 = top_margin
        y2 = bottom_margin
        
        return [(x1, y1), (x2, y2)]
    
    def _get_available_photos_for_human(self):
        """Get photos that haven't been chosen or excluded by human player"""
        # Extract photo IDs from chosen photos (which are now dicts with 'photo_id' and 'size')
        chosen_photo_ids = []
        for item in self.human_chosen_photos:
            if isinstance(item, dict):
                chosen_photo_ids.append(item['photo_id'])
            else:
                chosen_photo_ids.append(item)  # Fallback for old format
        
        excluded = set(chosen_photo_ids + self.human_excluded_photos)
        available = [p for p in PHOTO_POOL if p not in excluded]
        return available
    
    def _generate_human_options(self):
        """Generate 2 random photo options for human player"""
        available = self._get_available_photos_for_human()
        
        # Only proceed if we have at least 1 photo available
        if len(available) == 0:
            # No photos available - game should handle this gracefully
            self.human_current_options = []
            return
        
        # Select 1 or 2 photos depending on availability
        num_to_select = min(2, len(available))
        selected = random.sample(available, num_to_select)
        self.human_current_options = []
        
        # Get two non-overlapping positions
        positions = self._get_two_non_overlapping_positions()
        
        for i, photo_id in enumerate(selected):
            x, y = positions[i] if i < len(positions) else self._get_random_position()
            self.human_current_options.append(PhotoOption(photo_id, x, y))
        
        # Assign a random prompt for this pair of images (only unused prompts)
        available_prompts = [p for p in POETIC_PROMPTS if p not in self.used_prompts]
        if not available_prompts:
            # If all prompts used, reset and start over
            self.used_prompts = []
            available_prompts = POETIC_PROMPTS
        
        self.current_prompt = random.choice(available_prompts)
        if self.current_prompt not in self.used_prompts:
            self.used_prompts.append(self.current_prompt)
    
    def handle_human_selection(self, photo_id):
        """Handle human photo selection"""
        if self.game_complete or self.human_steps == 0:
            return False
        
        # Verify the photo is in current options
        selected_option = None
        for option in self.human_current_options:
            if option.photo_id == photo_id:
                selected_option = option
                break
        
        if not selected_option:
            return False
        
        # Get the size from the selected option (handle both PhotoOption objects and dicts)
        option_size = selected_option.size if hasattr(selected_option, 'size') else (selected_option.get('size') if isinstance(selected_option, dict) else 120)
        
        # Add selected photo to chosen photos with its size (for collage)
        self.human_chosen_photos.append({
            'photo_id': photo_id,
            'size': option_size
        })
        
        # Use the current prompt that was displayed with this selection
        prompt = self.current_prompt
        self.human_chosen_prompts.append({
            'photo_id': photo_id,
            'prompt': prompt
        })
        
        # Exclude the other photo from the current pair (the one that wasn't chosen)
        for option in self.human_current_options:
            if option.photo_id != photo_id and option.photo_id not in self.human_excluded_photos:
                self.human_excluded_photos.append(option.photo_id)
        
        self.human_steps -= 1
        
        # Generate new options
        if self.human_steps > 0:
            self._generate_human_options()
        
        self._update_completion_flag()
        return True
    
    def _update_completion_flag(self):
        """Mark the game as complete when human is out of steps"""
        if self.human_steps == 0:
            self.game_complete = True
    
    def start_game(self):
        """Start the game"""
        self.game_started = True
    
    def to_dict(self):
        """Convert game state to dictionary"""
        return {
            'human_steps': self.human_steps,
            'human_chosen_photos': self.human_chosen_photos,
            'human_chosen_prompts': self.human_chosen_prompts,
            'current_prompt': self.current_prompt,
            'human_current_options': [opt.to_dict() for opt in self.human_current_options],
            'game_complete': self.game_complete,
            'game_started': self.game_started,
            'width': self.width,
            'height': self.height
        }
    
    def generate_collage_data(self):
        """Generate collage layout data for chosen photos - 3 columns x 5 rows grid"""
        # Get list of photo IDs and sizes from chosen photos
        photos = [item['photo_id'] for item in self.human_chosen_photos]
        photo_sizes = {item['photo_id']: item['size'] for item in self.human_chosen_photos}
        
        if not photos:
            return []
        
        # Shuffle photos to randomize order in collage (not based on selection order)
        shuffled_photos = photos.copy()
        random.shuffle(shuffled_photos)
        
        # Fixed grid layout: 3 columns x 5 rows
        # Use cell size for positioning, but images will use original dimensions
        photos_per_row = 3
        cell_size = 100  # Grid cell size (positioning reference)
        spacing = 0  # No space between photos - they touch each other
        padding = 40  # Padding from edges
        
        # Calculate center position for the grid (left side of screen - Memory Collage)
        center_x = self.width / 4
        
        # Calculate total grid width (3 columns)
        total_width = photos_per_row * cell_size + (photos_per_row - 1) * spacing
        start_x = center_x - (total_width / 2) + (cell_size / 2)
        start_y = padding + 60  # Start below label area
        
        collage_items = []
        
        for i, photo_id in enumerate(shuffled_photos):
            # Calculate grid position (3 columns)
            row = i // photos_per_row
            col = i % photos_per_row
            
            x = start_x + col * (cell_size + spacing)
            y = start_y + row * (cell_size + spacing) + (cell_size / 2)
            
            # No rotation - keep photos straight
            rotation = 0
            
            # Use the stored size from selection (same size as when selected)
            stored_size = photo_sizes.get(photo_id, cell_size)
            
            collage_items.append({
                'photo_id': photo_id,
                'x': x,
                'y': y,
                'rotation': rotation,
                'size': stored_size,  # Use the same size as during selection
                'use_original_size': False,  # Use the stored size
                'z_index': i
            })
        
        return collage_items
    
    def generate_intuition_world_prompt(self):
        """Generate a prompt for the 3D Intuition World based on 4 randomly selected images"""
        if len(self.human_chosen_photos) < 4:
            # If less than 4, use all available
            selected_four = self.human_chosen_photos.copy()
        else:
            # Randomly select 4 images from the chosen photos
            selected_four = random.sample(self.human_chosen_photos, 4)
        
        # Extract photo_ids from the dictionaries
        selected_photo_ids = []
        for photo_item in selected_four:
            if isinstance(photo_item, dict):
                selected_photo_ids.append(photo_item['photo_id'])
            else:
                selected_photo_ids.append(photo_item)
        
        # Get prompts associated with these images
        selected_prompts = []
        for photo_id in selected_photo_ids:
            for prompt_data in self.human_chosen_prompts:
                if prompt_data['photo_id'] == photo_id:
                    selected_prompts.append(prompt_data['prompt'])
                    break
        
        # Create a combined prompt for the 3D world
        if selected_prompts:
            combined_prompt = f"Abstract 3D surrealist collage world combining: {', '.join(selected_prompts)}. Dreamlike landscape with fragmented elements, geometric shapes, floating structures, and ethereal atmosphere."
        else:
            combined_prompt = "Abstract 3D surrealist collage world with dreamlike landscape, fragmented elements, geometric shapes, and floating structures."
        
        # Return the photo_ids (not the full dictionaries) for the frontend
        return selected_photo_ids, selected_prompts, combined_prompt
    
    def get_dominant_color_from_selections(self):
        """Extract a dominant color from one of the selected images for gradient"""
        # For now, return a default color palette based on common surrealist colors
        # In a full implementation, you would analyze the actual images
        color_palette = [
            {'r': 200, 'g': 100, 'b': 50},   # Orange-red
            {'r': 50, 'g': 100, 'b': 200},  # Blue
            {'r': 100, 'g': 50, 'b': 100},  # Purple
            {'r': 150, 'g': 150, 'b': 100}, # Olive
            {'r': 200, 'g': 150, 'b': 100}, # Tan
        ]
        
        if self.human_chosen_photos:
            # Randomly select a color from the palette
            return random.choice(color_palette)
        return {'r': 150, 'g': 150, 'b': 150}  # Default gray


@app.route('/')
def index():
    """Main game page"""
    return render_template('index.html')


@app.route('/images/<filename>')
def serve_image(filename):
    """Serve images from the images directory without any modification"""
    # Get the full path
    image_path = IMAGES_DIR / filename
    
    # Security check: ensure file exists and is in the images directory
    if not image_path.exists() or not image_path.is_file():
        return jsonify({'error': 'Image not found'}), 404
    
    # Security check: ensure the file is actually inside IMAGES_DIR
    try:
        image_path.resolve().relative_to(IMAGES_DIR.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 403
    
    # Determine content type based on extension
    content_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    ext = image_path.suffix.lower()
    content_type = content_type_map.get(ext, 'application/octet-stream')
    
    # Send file with headers to prevent compression and modification
    response = send_from_directory(IMAGES_DIR, filename, mimetype=content_type)
    
    # Set headers to prevent any compression or modification
    response.headers['Cache-Control'] = 'no-transform, public, max-age=31536000'
    response.headers['Content-Encoding'] = 'identity'  # Disable any encoding
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    return response

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files"""
    audio_path = AUDIO_DIR / filename
    if not audio_path.exists():
        return jsonify({'error': 'Audio file not found'}), 404
    
    # Security check: ensure the file is actually inside AUDIO_DIR
    try:
        audio_path.resolve().relative_to(AUDIO_DIR.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 403
    
    # Determine content type based on extension
    content_type_map = {
        '.mp3': 'audio/mpeg',
        '.mpeg': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg'
    }
    
    ext = audio_path.suffix.lower()
    content_type = content_type_map.get(ext, 'application/octet-stream')
    
    # Send file with headers
    response = send_from_directory(AUDIO_DIR, filename, mimetype=content_type)
    response.headers['Cache-Control'] = 'public, max-age=31536000'
    
    return response


@app.route('/api/game/new', methods=['POST'])
def new_game():
    """Create a new game"""
    game_id = str(random.randint(1000, 9999))
    game_states[game_id] = GameState(game_id)
    return jsonify({'game_id': game_id})


@app.route('/api/game/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    """Get current game state"""
    if game_id not in game_states:
        return jsonify({'error': 'Game not found'}), 404
    
    return jsonify(game_states[game_id].to_dict())


@app.route('/api/game/<game_id>/start', methods=['POST'])
def start_game(game_id):
    """Start the game"""
    if game_id not in game_states:
        return jsonify({'error': 'Game not found'}), 404
    
    game_states[game_id].start_game()
    return jsonify({'success': True})


@app.route('/api/game/<game_id>/select', methods=['POST'])
def handle_selection(game_id):
    """Handle human photo selection"""
    try:
        if game_id not in game_states:
            return jsonify({'error': 'Game not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        photo_id = data.get('photo_id')
        
        if photo_id is None:
            return jsonify({'error': 'Missing photo_id'}), 400
        
        success = game_states[game_id].handle_human_selection(photo_id)
        return jsonify({'success': success, 'state': game_states[game_id].to_dict()})
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"Error in handle_selection: {error_msg}")
        print(traceback_str)
        return jsonify({'error': error_msg, 'traceback': traceback_str}), 500




@app.route('/api/game/<game_id>/collage', methods=['GET'])
def get_collage(game_id):
    """Get collage data"""
    if game_id not in game_states:
        return jsonify({'error': 'Game not found'}), 404
    
    collage_data = game_states[game_id].generate_collage_data()
    return jsonify({'collage': collage_data})


def generate_poem_from_prompts(prompts):
    """Generate poetry with specific constraints:
    - Include 4 image texts verbatim exactly once (no repeats)
    - Don't use prompts in title (first line)
    - Use at least 3 sensory details (sound/smell/touch/etc.)
    - Include exactly one question mark
    - Length: 15-19 lines
    """
    if not prompts or len(prompts) == 0:
        return [
            'Whispers in the void',
            'Memories fade like mist',
            'Echoes remain'
        ]
    
    # Ensure we have exactly 4 prompts
    if len(prompts) < 4:
        prompts = prompts + [''] * (4 - len(prompts))
    prompts = prompts[:4]
    
    # Filter out empty prompts
    valid_prompts = [p for p in prompts if p and p.strip()]
    if len(valid_prompts) < 4:
        valid_prompts = valid_prompts + [''] * (4 - len(valid_prompts))
    prompts = valid_prompts[:4]
    
    # Sensory detail phrases (more natural)
    sensory_phrases = {
        'sound': [
            'a whisper echoes', 'silence rings', 'a hum drifts', 'chimes crack', 'murmurs rise', 'buzzes fade',
            'echoes fade', 'voices crack', 'sounds dissolve', 'noise settles', 'tones drift', 'notes float',
            'rhythms pulse', 'beats fade', 'harmonies break', 'melodies shatter', 'songs fragment', 'music distorts',
            'cries echo', 'screams fade', 'laughter rings', 'sighs drift', 'breaths whisper', 'heartbeats thud',
            'footsteps fade', 'doors creak', 'windows rattle', 'walls vibrate', 'floors groan', 'ceilings hum',
            'winds howl', 'storms roar', 'rains patter', 'thunder rumbles', 'lightning cracks', 'hail clatters',
            'waves crash', 'tides ebb', 'currents flow', 'streams babble', 'rivers rush', 'oceans roar',
            'leaves rustle', 'branches snap', 'trees creak', 'forests whisper', 'fields hum', 'meadows sing',
            'machines whir', 'engines roar', 'gears grind', 'wheels turn', 'cogs click', 'chains rattle',
            'bells toll', 'gongs ring', 'drums beat', 'cymbals clash', 'strings pluck', 'horns blare',
            'static crackles', 'frequencies shift', 'wavelengths bend', 'resonance builds', 'vibrations fade', 'oscillations stop',
            'silence breaks', 'quiet deepens', 'stillness speaks', 'hush falls', 'calm whispers', 'peace rings'
        ],
        'smell': [
            'scent of rust', 'odor of decay', 'fragrance drifts', 'stench rises', 'aroma settles', 'perfume lingers',
            'smell of rain', 'odor of earth', 'scent of metal', 'fragrance of flowers', 'aroma of coffee', 'perfume of smoke',
            'stench of rot', 'odor of mold', 'scent of dust', 'fragrance of paper', 'aroma of ink', 'perfume of leather',
            'smell of salt', 'odor of sea', 'scent of wind', 'fragrance of grass', 'aroma of wood', 'perfume of pine',
            'stench of sulfur', 'odor of ozone', 'scent of electricity', 'fragrance of oil', 'aroma of gasoline', 'perfume of exhaust',
            'smell of food', 'odor of cooking', 'scent of bread', 'fragrance of spices', 'aroma of herbs', 'perfume of vanilla',
            'stench of garbage', 'odor of waste', 'scent of decay', 'fragrance of compost', 'aroma of soil', 'perfume of moss',
            'smell of morning', 'odor of night', 'scent of dawn', 'fragrance of dusk', 'aroma of noon', 'perfume of midnight',
            'stench of fear', 'odor of sweat', 'scent of blood', 'fragrance of tears', 'aroma of breath', 'perfume of skin',
            'smell of old', 'odor of new', 'scent of ancient', 'fragrance of fresh', 'aroma of stale', 'perfume of clean',
            'stench of burning', 'odor of ash', 'scent of smoke', 'fragrance of embers', 'aroma of char', 'perfume of fire',
            'smell of cold', 'odor of heat', 'scent of ice', 'fragrance of steam', 'aroma of frost', 'perfume of warmth',
            'stench of chemicals', 'odor of medicine', 'scent of alcohol', 'fragrance of bleach', 'aroma of disinfectant', 'perfume of antiseptic',
            'smell of memory', 'odor of nostalgia', 'scent of longing', 'fragrance of regret', 'aroma of hope', 'perfume of dreams',
            'stench of truth', 'odor of lies', 'scent of secrets', 'fragrance of mystery', 'aroma of knowledge', 'perfume of wisdom',
            'smell fades', 'odor lingers', 'scent drifts', 'fragrance settles', 'aroma rises', 'perfume evaporates'
        ],
        'touch': [
            'cold surfaces', 'warm edges', 'rough textures', 'smooth planes', 'icy fragments', 'sharp corners', 'soft curves',
            'hot metal', 'cool glass', 'warm wood', 'cold stone', 'icy water', 'burning sand', 'freezing air',
            'rough bark', 'smooth silk', 'coarse fabric', 'fine grain', 'gritty sand', 'slippery ice', 'sticky resin',
            'sharp blades', 'dull edges', 'pointed tips', 'rounded forms', 'jagged shards', 'polished surfaces', 'matte finishes',
            'hard concrete', 'soft cushions', 'firm ground', 'yielding foam', 'rigid steel', 'flexible rubber', 'brittle glass',
            'wet rain', 'dry dust', 'moist earth', 'arid desert', 'damp cloth', 'soaked fabric', 'parched skin',
            'sticky honey', 'slippery oil', 'gritty dirt', 'smooth marble', 'rough stone', 'polished brass', 'tarnished silver',
            'prickly thorns', 'velvety petals', 'coarse hair', 'fine silk', 'thick fur', 'thin paper', 'dense foam',
            'bumpy roads', 'smooth paths', 'uneven ground', 'level surfaces', 'steep slopes', 'gentle curves', 'sharp angles',
            'tender flesh', 'tough hide', 'delicate skin', 'calloused hands', 'smooth palms', 'rough knuckles', 'soft fingertips',
            'burning fire', 'freezing ice', 'scorching sun', 'chilling wind', 'warm embrace', 'cold rejection', 'lukewarm indifference',
            'vibrating strings', 'static surfaces', 'pulsing rhythms', 'steady beats', 'irregular patterns', 'smooth flows', 'jerky motions',
            'pressure builds', 'tension releases', 'stress fractures', 'relief flows', 'weight presses', 'lightness lifts', 'gravity pulls',
            'friction grinds', 'lubrication slides', 'resistance pushes', 'yielding gives', 'rigidity holds', 'flexibility bends', 'elasticity snaps',
            'texture shifts', 'surface changes', 'form transforms', 'shape morphs', 'structure alters', 'pattern breaks', 'design reforms',
            'touch fades', 'sensation lingers', 'feeling drifts', 'contact breaks', 'connection forms', 'bond strengthens', 'link weakens'
        ],
        'taste': [
            'bitter air', 'sweet mist', 'metallic tang', 'sour breath',
            'salty tears', 'sweet honey', 'sour lemons', 'bitter coffee', 'spicy peppers', 'bland rice',
            'tangy vinegar', 'savory broth', 'umami depth', 'acidic wine', 'alkaline water', 'neutral milk',
            'sweet sugar', 'bitter chocolate', 'sour grapes', 'salty chips', 'spicy curry', 'mild cheese',
            'tart apples', 'ripe berries', 'fresh mint', 'earthy mushrooms', 'woody herbs', 'floral tea',
            'metallic blood', 'coppery coins', 'iron filings', 'zinc tablets', 'aluminum foil', 'tin cans',
            'sweet memories', 'bitter regrets', 'sour disappointments', 'salty tears', 'spicy arguments', 'bland routines',
            'tangy nostalgia', 'savory moments', 'umami experiences', 'acidic relationships', 'alkaline peace', 'neutral existence',
            'sweet success', 'bitter failure', 'sour grapes', 'salty language', 'spicy gossip', 'mild conversation',
            'tart criticism', 'ripe opportunities', 'fresh ideas', 'earthy wisdom', 'woody knowledge', 'floral inspiration',
            'metallic truth', 'coppery lies', 'iron will', 'zinc determination', 'aluminum dreams', 'tin reality',
            'sweet dreams', 'bitter reality', 'sour truth', 'salty honesty', 'spicy passion', 'bland apathy',
            'tangy excitement', 'savory satisfaction', 'umami fulfillment', 'acidic anger', 'alkaline calm', 'neutral balance',
            'sweet love', 'bitter hate', 'sour jealousy', 'salty envy', 'spicy desire', 'mild affection',
            'tart rejection', 'ripe acceptance', 'fresh beginnings', 'earthy endings', 'woody transitions', 'floral transformations',
            'metallic futures', 'coppery pasts', 'iron presents', 'zinc memories', 'aluminum hopes', 'tin fears',
            'taste fades', 'flavor lingers', 'sensation drifts', 'palate clears', 'tongue remembers', 'mouth forgets', 'senses blend'
        ],
        'sight': [
            'glowing forms', 'shimmering edges', 'glimmering shapes', 'flashing lights', 'sparkling dust', 'radiant haze',
            'bright stars', 'dim shadows', 'vivid colors', 'muted tones', 'sharp lines', 'blurred edges', 'clear vision',
            'dazzling sun', 'gentle moon', 'fierce lightning', 'soft glow', 'harsh glare', 'warm light', 'cold illumination',
            'vibrant reds', 'deep blues', 'bright yellows', 'rich greens', 'pure whites', 'absolute blacks', 'endless grays',
            'geometric patterns', 'organic shapes', 'abstract forms', 'concrete structures', 'fluid movements', 'static positions', 'dynamic flows',
            'distant horizons', 'close details', 'wide panoramas', 'narrow focus', 'deep perspectives', 'flat surfaces', 'curved spaces',
            'sharp contrasts', 'smooth gradients', 'bold strokes', 'fine lines', 'thick borders', 'thin boundaries', 'broken edges',
            'crystal clarity', 'foggy obscurity', 'transparent layers', 'opaque barriers', 'translucent veils', 'reflective surfaces', 'absorbent materials',
            'brilliant highlights', 'deep shadows', 'mid tones', 'high contrast', 'low contrast', 'balanced exposure', 'extreme values',
            'moving objects', 'still life', 'frozen moments', 'flowing time', 'captured motion', 'blurred movement', 'sharp stillness',
            'geometric precision', 'organic chaos', 'structured randomness', 'ordered disorder', 'patterned chaos', 'chaotic patterns', 'random order',
            'distant mountains', 'close flowers', 'wide skies', 'narrow paths', 'deep valleys', 'flat plains', 'curved roads',
            'sharp peaks', 'smooth valleys', 'rough terrain', 'polished surfaces', 'jagged rocks', 'rounded stones', 'angular crystals',
            'bright futures', 'dark pasts', 'clear presents', 'blurred memories', 'sharp recollections', 'faded images', 'vivid dreams',
            'glowing hopes', 'dimming fears', 'shimmering possibilities', 'glimmering doubts', 'flashing insights', 'sparkling ideas', 'radiant understanding',
            'dazzling truth', 'gentle lies', 'fierce honesty', 'soft deception', 'harsh reality', 'warm illusions', 'cold facts',
            'vibrant emotions', 'deep feelings', 'bright passions', 'rich experiences', 'pure intentions', 'absolute actions', 'endless thoughts',
            'geometric logic', 'organic intuition', 'abstract concepts', 'concrete facts', 'fluid reasoning', 'static beliefs', 'dynamic understanding',
            'distant goals', 'close achievements', 'wide perspectives', 'narrow views', 'deep insights', 'flat understanding', 'curved knowledge',
            'sharp focus', 'blurred awareness', 'clear perception', 'foggy comprehension', 'transparent meaning', 'opaque confusion', 'translucent understanding',
            'brilliant clarity', 'deep mystery', 'mid ambiguity', 'high certainty', 'low confidence', 'balanced uncertainty', 'extreme conviction',
            'moving forward', 'still backward', 'frozen present', 'flowing future', 'captured past', 'blurred timeline', 'sharp moment',
            'sight fades', 'vision lingers', 'image drifts', 'form dissolves', 'shape reforms', 'pattern breaks', 'design emerges'
        ]
    }
    
    # Poetic building blocks
    poetic_elements = [
        'beneath the surface', 'above the void', 'within the space', 'through the gap',
        'across the divide', 'beyond the edge', 'between the lines', 'where shadows meet',
        'when time stops', 'how light bends', 'if gravity fails', 'as memory fades',
        'like dust settling', 'unlike before', 'drifts slowly', 'flows upward',
        'settles down', 'rises high', 'falls apart', 'shifts position',
        'turns around', 'bends inward', 'breaks open', 'forms patterns',
        'dissolves away', 'merges together', 'separates cleanly', 'connects points',
        'disconnects fully', 'empty spaces', 'full moments', 'vast distances',
        'tiny fragments', 'ancient echoes', 'new beginnings', 'frozen time',
        'melting edges', 'fragmented whole', 'complete nothing',
        'under the weight', 'over the horizon', 'inside the silence', 'outside the frame',
        'along the border', 'against the current', 'beside the void', 'where light breaks',
        'as sound fades', 'while colors shift', 'until shadows merge', 'since time began',
        'like waves crashing', 'unlike the past', 'drifts sideways', 'flows downward',
        'settles inward', 'rises beyond', 'falls together', 'shifts perspective',
        'turns inside out', 'bends backward', 'breaks free', 'forms connections',
        'dissolves into', 'merges with', 'separates from', 'connects to',
        'disconnects from', 'hollow spaces', 'dense moments', 'infinite distances',
        'minute particles', 'distant whispers', 'endless cycles', 'suspended motion',
        'crystallizing thoughts', 'shattered unity', 'incomplete everything',
        'through the mirror', 'around the corner', 'inside the echo', 'outside the dream',
        'along the thread', 'against the grain', 'beside the truth', 'where darkness meets',
        'as voices blend', 'while shapes transform', 'until colors fade', 'since space curved',
        'like memories floating', 'unlike tomorrow', 'drifts forward', 'flows backward',
        'settles nowhere', 'rises everywhere', 'falls upward', 'shifts dimensions',
        'turns invisible', 'bends reality', 'breaks silence', 'forms chaos',
        'dissolves structure', 'merges opposites', 'separates unity', 'connects fragments',
        'disconnects bonds', 'void spaces', 'solid moments', 'endless horizons',
        'infinite particles', 'eternal whispers', 'timeless cycles', 'motionless motion',
        'fluid boundaries', 'static flow', 'dynamic stillness',
        'below the threshold', 'above the noise', 'within the pause', 'through the veil',
        'across the chasm', 'beyond the veil', 'between the breaths', 'where silence speaks',
        'when matter dissolves', 'how shadows dance', 'if sound becomes light', 'as form escapes',
        'like thoughts crystallize', 'unlike the expected', 'drifts aimlessly', 'flows in circles',
        'settles like mist', 'rises like smoke', 'falls like feathers', 'shifts like sand',
        'turns to stone', 'bends like glass', 'breaks like dawn', 'forms like clouds',
        'dissolves like sugar', 'merges like rivers', 'separates like oil', 'connects like roots',
        'disconnects like stars', 'hollow echoes', 'dense fog', 'infinite loops',
        'minute vibrations', 'distant thunder', 'endless repetition', 'suspended disbelief',
        'crystallizing doubt', 'shattered expectations', 'incomplete sentences',
        'through the prism', 'around the bend', 'inside the pause', 'outside the circle',
        'along the curve', 'against the flow', 'beside the absence', 'where meaning breaks',
        'as texture fades', 'while volume shifts', 'until form merges', 'since structure collapsed',
        'like gravity reverses', 'unlike the known', 'drifts in reverse', 'flows against itself',
        'settles in layers', 'rises in spirals', 'falls in fragments', 'shifts in waves',
        'turns to liquid', 'bends to breaking', 'breaks to pieces', 'forms to nothing',
        'dissolves to essence', 'merges to one', 'separates to many', 'connects to all',
        'disconnects to none', 'void between', 'solid between', 'endless between',
        'infinite between', 'eternal between', 'timeless between', 'motionless between',
        'fluid between', 'static between', 'dynamic between',
        'underneath the layers', 'overhead the clouds', 'inside the core', 'outside the shell',
        'alongside the path', 'against the wind', 'beside the absence', 'where time curves',
        'as space folds', 'while matter shifts', 'until energy fades', 'since consciousness began',
        'like atoms dance', 'unlike the pattern', 'drifts in patterns', 'flows in streams',
        'settles in pools', 'rises in columns', 'falls in sheets', 'shifts in grids',
        'turns to vapor', 'bends to will', 'breaks to atoms', 'forms to energy',
        'dissolves to light', 'merges to sound', 'separates to color', 'connects to thought',
        'disconnects to void', 'hollow resonance', 'dense emptiness', 'infinite singularity',
        'minute infinity', 'distant proximity', 'endless moment', 'suspended eternity',
        'crystallizing void', 'shattered infinity', 'incomplete completion',
        'through the threshold', 'around the axis', 'inside the matrix', 'outside the system',
        'along the spectrum', 'against the order', 'beside the chaos', 'where order meets chaos',
        'as logic fails', 'while reason bends', 'until sense breaks', 'since meaning dissolved',
        'like truth shifts', 'unlike the absolute', 'drifts in uncertainty', 'flows in paradox',
        'settles in contradiction', 'rises in harmony', 'falls in discord', 'shifts in balance',
        'turns to question', 'bends to answer', 'breaks to mystery', 'forms to riddle',
        'dissolves to truth', 'merges to lie', 'separates to both', 'connects to neither',
        'disconnects to all', 'void of meaning', 'solid of meaning', 'endless of meaning',
        'infinite of meaning', 'eternal of meaning', 'timeless of meaning', 'motionless of meaning',
        'fluid of meaning', 'static of meaning', 'dynamic of meaning',
        'beneath the layers', 'above the clouds', 'within the core', 'through the shell',
        'across the path', 'beyond the wind', 'between the absence', 'where curves meet',
        'when space folds', 'how matter shifts', 'if energy fades', 'as consciousness began',
        'like patterns dance', 'unlike the stream', 'drifts in circles', 'flows in patterns',
        'settles in mist', 'rises in smoke', 'falls in feathers', 'shifts in sand',
        'turns to dawn', 'bends to glass', 'breaks to stone', 'forms to clouds',
        'dissolves to roots', 'merges to rivers', 'separates to oil', 'connects to sugar',
        'disconnects to stars', 'hollow like echoes', 'dense like fog', 'infinite like loops',
        'minute like vibrations', 'distant like thunder', 'endless like repetition', 'suspended like disbelief',
        'crystallizing like doubt', 'shattered like expectations', 'incomplete like sentences',
        'through the pause', 'around the circle', 'inside the prism', 'outside the bend',
        'along the absence', 'against the meaning', 'beside the curve', 'where texture breaks',
        'as volume fades', 'while form shifts', 'until structure merges', 'since gravity collapsed',
        'like known reverses', 'unlike the liquid', 'drifts to breaking', 'flows to pieces',
        'settles to nothing', 'rises to essence', 'falls to one', 'shifts to many',
        'turns to all', 'bends to none', 'breaks to between', 'forms to void',
        'dissolves to solid', 'merges to endless', 'separates to infinite', 'connects to eternal',
        'disconnects to timeless', 'hollow to motionless', 'dense to fluid', 'infinite to static',
        'minute to dynamic', 'distant to layers', 'endless to clouds', 'suspended to core',
        'crystallizing to shell', 'shattered to path', 'incomplete to absence',
        'underneath the curves', 'overhead the space', 'inside the matter', 'outside the energy',
        'alongside the consciousness', 'against the atoms', 'beside the patterns', 'where streams meet',
        'as circles dance', 'while mist flows', 'until smoke settles', 'since feathers rise',
        'like sand falls', 'unlike the vapor', 'drifts to will', 'flows to atoms',
        'settles to energy', 'rises to light', 'falls to sound', 'shifts to color',
        'turns to thought', 'bends to void', 'breaks to resonance', 'forms to emptiness',
        'dissolves to singularity', 'merges to infinity', 'separates to proximity', 'connects to moment',
        'disconnects to eternity', 'hollow to void', 'dense to infinity', 'infinite to completion',
        'minute to threshold', 'distant to axis', 'endless to matrix', 'suspended to system',
        'crystallizing to spectrum', 'shattered to order', 'incomplete to chaos',
        'through the logic', 'around the reason', 'inside the sense', 'outside the meaning',
        'along the truth', 'against the absolute', 'beside the uncertainty', 'where paradox meets',
        'as contradiction shifts', 'while harmony rises', 'until discord falls', 'since balance breaks',
        'like question turns', 'unlike the answer', 'drifts to mystery', 'flows to riddle',
        'settles to truth', 'rises to lie', 'falls to both', 'shifts to neither',
        'turns to all', 'bends to meaning', 'breaks to void', 'forms to solid',
        'dissolves to endless', 'merges to infinite', 'separates to eternal', 'connects to timeless',
        'disconnects to motionless', 'hollow to fluid', 'dense to static', 'infinite to dynamic'
    ]
    
    # Build poem structure
    poem = []
    prompt_inserted = [False] * 4
    question_added = False
    sensory_used = {'sound': False, 'smell': False, 'touch': False, 'taste': False, 'sight': False}
    used_lines = set()  # Track all lines to prevent duplicates (normalized to lowercase)
    available_sensory_phrases = {k: v.copy() for k, v in sensory_phrases.items()}  # Copy to remove used ones
    available_poetic_elements = poetic_elements.copy()  # Copy to remove used ones
    
    # Target: 15-19 lines
    target_lines = random.randint(15, 19)
    
    # Shuffle prompts to randomize insertion order
    prompt_order = list(range(4))
    random.shuffle(prompt_order)
    prompt_insertion_positions = []
    
    # Generate base poem lines (without prompts)
    line_count = 0
    max_attempts = 200  # Prevent infinite loops
    
    while line_count < target_lines - 4:  # Reserve space for 4 prompts
        attempts = 0
        line_added = False
        
        # Add sensory detail (ensure at least 3 different types)
        if not all(list(sensory_used.values())[:3]):  # Need at least 3 types
            sensory_type = random.choice(['sound', 'smell', 'touch', 'taste', 'sight'])
            if not sensory_used[sensory_type] and available_sensory_phrases[sensory_type]:
                sensory_phrase = random.choice(available_sensory_phrases[sensory_type])
                line_text = sensory_phrase.capitalize()
                line_lower = line_text.lower()
                if line_lower not in used_lines:
                    poem.append(line_text)
                    used_lines.add(line_lower)
                    available_sensory_phrases[sensory_type].remove(sensory_phrase)
                    sensory_used[sensory_type] = True
                    line_count += 1
                    line_added = True
                    continue
        
        if not line_added:
            # Add regular poetic line (ensure no duplicates)
            while attempts < max_attempts and not line_added:
                if random.random() < 0.7:
                    # Use single element
                    if available_poetic_elements:
                        element = random.choice(available_poetic_elements)
                        line_text = element.capitalize()
                        line_lower = line_text.lower()
                        # Check for exact duplicate
                        if line_lower not in used_lines:
                            poem.append(line_text)
                            used_lines.add(line_lower)
                            available_poetic_elements.remove(element)
                            line_count += 1
                            line_added = True
                            break
                else:
                    # Combine elements
                    if len(available_poetic_elements) >= 2:
                        part1 = random.choice(available_poetic_elements)
                        remaining = [e for e in available_poetic_elements if e != part1]
                        part2 = random.choice(remaining)
                        
                        if random.random() < 0.5:
                            line_text = f"{part1}, {part2}".capitalize()
                        else:
                            line_text = f"{part1} {part2}".capitalize()
                        
                        # Check for exact duplicate and key phrase overlap
                        line_lower = line_text.lower()
                        if line_lower not in used_lines:
                            # Check for significant word overlap with existing lines
                            words = set(line_lower.replace(',', '').split())
                            is_duplicate = False
                            for used_line in used_lines:
                                used_words = set(used_line.replace(',', '').split())
                                # If more than 2 key words overlap, consider it too similar
                                overlap = words & used_words
                                if len(overlap) > 2 and len(overlap) / max(len(words), len(used_words)) > 0.4:
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                poem.append(line_text)
                                used_lines.add(line_lower)
                                # Always remove elements to prevent reuse
                                if part1 in available_poetic_elements:
                                    available_poetic_elements.remove(part1)
                                if part2 in available_poetic_elements:
                                    available_poetic_elements.remove(part2)
                                line_count += 1
                                line_added = True
                                break
                
                attempts += 1
            
            # Fallback if we can't find a unique line
            if not line_added:
                fallback_text = f"in the space between {line_count}".capitalize()
                fallback_lower = fallback_text.lower()
                if fallback_lower not in used_lines:
                    poem.append(fallback_text)
                    used_lines.add(fallback_lower)
                    line_count += 1
                else:
                    # Last resort: just increment to avoid infinite loop
                    line_count += 1
    
    # Insert prompts verbatim at random positions (not first line, not consecutive)
    prompt_positions = []
    for i, prompt_idx in enumerate(prompt_order):
        if prompts[prompt_idx] and prompts[prompt_idx].strip():
            # Find insertion position (avoid first line, avoid consecutive)
            attempts = 0
            while attempts < 20:
                insert_pos = random.randint(2, len(poem) - 1)
                # Check not too close to other prompts
                too_close = any(abs(insert_pos - pos) < 2 for pos in prompt_positions)
                if not too_close:
                    poem.insert(insert_pos, prompts[prompt_idx])
                    prompt_positions.append(insert_pos)
                    prompt_inserted[prompt_idx] = True
                    break
                attempts += 1
            if attempts >= 20:
                # Fallback: insert at end
                poem.append(prompts[prompt_idx])
                prompt_positions.append(len(poem) - 1)
                prompt_inserted[prompt_idx] = True
    
    # Ensure at least 3 sensory details are present
    sensory_count = sum(1 for used in sensory_used.values() if used)
    if sensory_count < 3:
        missing_types = [stype for stype, used in sensory_used.items() if not used]
        needed = 3 - sensory_count
        for stype in missing_types[:needed]:
            sensory_phrase = random.choice(sensory_phrases[stype])
            insert_pos = random.randint(1, len(poem) - 2)
            poem.insert(insert_pos, sensory_phrase.capitalize())
            sensory_used[stype] = True
    
    # Add exactly one question mark
    if not question_added:
        # Find a line to add question (not first, not last, not a prompt line)
        question_candidates = []
        for i, line in enumerate(poem):
            if i > 0 and i < len(poem) - 1 and i not in prompt_positions:
                question_candidates.append(i)
        
        if question_candidates:
            q_pos = random.choice(question_candidates)
            # Add question word or convert to question
            if random.random() < 0.5:
                poem[q_pos] = poem[q_pos].rstrip('.') + ' what remains?'
            else:
                # Convert statement to question
                line = poem[q_pos].rstrip('.')
                if line.endswith('s'):
                    poem[q_pos] = line + ' what?'
                else:
                    poem[q_pos] = line + ', what then?'
            question_added = True
    
    # Ensure exactly one question mark (remove extras)
    question_count = sum(1 for line in poem if '?' in line)
    if question_count > 1:
        found_first = False
        for i, line in enumerate(poem):
            if '?' in line:
                if not found_first:
                    found_first = True
                else:
                    poem[i] = line.replace('?', '.')
    
    # Trim to 15-19 lines
    if len(poem) < 15:
        while len(poem) < 15:
            poem.append('In the space between')
    elif len(poem) > 19:
        poem = poem[:19]
    
    # Return poem and insertion positions for reference
    return poem


@app.route('/api/game/<game_id>/intuition-world', methods=['GET'])
def get_intuition_world(game_id):
    """Get intuition world generation data"""
    if game_id not in game_states:
        return jsonify({'error': 'Game not found'}), 404
    
    selected_images, selected_prompts, combined_prompt = game_states[game_id].generate_intuition_world_prompt()
    dominant_color = game_states[game_id].get_dominant_color_from_selections()
    
    # Generate poem from prompts using Markov chain
    generated_poem = []
    if selected_prompts and len(selected_prompts) > 0:
        generated_poem = generate_poem_from_prompts(selected_prompts)
    
    return jsonify({
        'selected_images': selected_images or [],
        'selected_prompts': selected_prompts or [],
        'generation_prompt': combined_prompt,
        'dominant_color': dominant_color,
        'generated_poem': generated_poem
    })


@app.route('/api/photos', methods=['GET'])
def get_photo_list():
    """Get list of available photos"""
    # Refresh photo pool
    global PHOTO_POOL
    PHOTO_POOL = get_photo_pool()
    return jsonify({'photos': PHOTO_POOL, 'count': len(PHOTO_POOL)})


@app.route('/api/photos/<filename>/dimensions', methods=['GET'])
def get_photo_dimensions(filename):
    """Get dimensions of a specific PNG image"""
    dimensions = get_image_dimensions(filename)
    if dimensions:
        return jsonify(dimensions)
    return jsonify({'error': 'Image not found'}), 404


if __name__ == '__main__':
    # Disable compression middleware for images
    from werkzeug.middleware.proxy_fix import ProxyFix
    # Run without compression
    app.run(debug=True, port=5000, threaded=True)
