"""
Presentation template configurations and styling definitions.
"""
from typing import Dict, Any
from pptx.dml.color import RGBColor
from pptx.util import Pt

class PresentationTemplates:
    """Template configurations for different presentation types."""
    
    TEMPLATE_CONFIGS = {
        'executive': {
            'name': 'Executive Business',
            'description': 'Clean, corporate design for business presentations',
            'colors': {
                'primary': RGBColor(30, 58, 138),     # Navy blue
                'secondary': RGBColor(245, 158, 11),   # Gold
                'accent': RGBColor(255, 255, 255),     # White
                'text': RGBColor(31, 41, 55),          # Dark gray
                'background': RGBColor(248, 250, 252)  # Light gray
            },
            'fonts': {
                'title': {'name': 'Calibri', 'size': Pt(36), 'bold': True},
                'subtitle': {'name': 'Calibri', 'size': Pt(24), 'bold': False},
                'content': {'name': 'Calibri', 'size': Pt(18), 'bold': False},
                'notes': {'name': 'Calibri', 'size': Pt(14), 'bold': False}
            },
            'slide_types': {
                'title': 0,
                'content': 1,
                'two_column': 2,
                'comparison': 3,
                'blank': 6
            }
        },
        
        'technical': {
            'name': 'Technical Solution',
            'description': 'Modern, tech-forward design for technical presentations',
            'colors': {
                'primary': RGBColor(14, 165, 233),     # Tech blue
                'secondary': RGBColor(16, 185, 129),    # Tech green
                'accent': RGBColor(55, 65, 81),         # Dark gray
                'text': RGBColor(243, 244, 246),        # Light gray
                'background': RGBColor(17, 24, 39)      # Dark background
            },
            'fonts': {
                'title': {'name': 'Segoe UI', 'size': Pt(36), 'bold': True},
                'subtitle': {'name': 'Segoe UI', 'size': Pt(24), 'bold': False},
                'content': {'name': 'Segoe UI', 'size': Pt(18), 'bold': False},
                'notes': {'name': 'Segoe UI', 'size': Pt(14), 'bold': False}
            },
            'slide_types': {
                'title': 0,
                'content': 1,
                'two_column': 2,
                'comparison': 3,
                'blank': 6
            }
        },
        
        'marketing': {
            'name': 'Marketing Pitch',
            'description': 'Dynamic, engaging design for marketing presentations',
            'colors': {
                'primary': RGBColor(139, 92, 246),     # Purple
                'secondary': RGBColor(236, 72, 153),    # Pink
                'accent': RGBColor(249, 115, 22),       # Orange
                'text': RGBColor(17, 24, 39),           # Dark text
                'background': RGBColor(255, 255, 255)   # White background
            },
            'fonts': {
                'title': {'name': 'Arial', 'size': Pt(40), 'bold': True},
                'subtitle': {'name': 'Arial', 'size': Pt(26), 'bold': False},
                'content': {'name': 'Arial', 'size': Pt(20), 'bold': False},
                'notes': {'name': 'Arial', 'size': Pt(14), 'bold': False}
            },
            'slide_types': {
                'title': 0,
                'content': 1,
                'two_column': 2,
                'comparison': 3,
                'blank': 6
            }
        },
        
        'strategy': {
            'name': 'Strategy Overview',
            'description': 'Professional, framework-focused design for strategic presentations',
            'colors': {
                'primary': RGBColor(59, 130, 246),     # Blue
                'secondary': RGBColor(55, 65, 81),      # Gray
                'accent': RGBColor(156, 163, 175),      # Light gray
                'text': RGBColor(31, 41, 55),           # Dark gray
                'background': RGBColor(255, 255, 255)   # White background
            },
            'fonts': {
                'title': {'name': 'Calibri', 'size': Pt(38), 'bold': True},
                'subtitle': {'name': 'Calibri', 'size': Pt(24), 'bold': False},
                'content': {'name': 'Calibri', 'size': Pt(18), 'bold': False},
                'notes': {'name': 'Calibri', 'size': Pt(14), 'bold': False}
            },
            'slide_types': {
                'title': 0,
                'content': 1,
                'two_column': 2,
                'comparison': 3,
                'blank': 6
            }
        }
    }
    
    @classmethod
    def get_template_config(cls, template_type: str) -> Dict[str, Any]:
        """Get template configuration by type."""
        return cls.TEMPLATE_CONFIGS.get(template_type, cls.TEMPLATE_CONFIGS['executive'])
    
    @classmethod
    def get_available_templates(cls) -> List[str]:
        """Get list of available template types."""
        return list(cls.TEMPLATE_CONFIGS.keys())
    
    @classmethod
    def get_template_info(cls, template_type: str) -> Dict[str, str]:
        """Get basic info about a template."""
        config = cls.get_template_config(template_type)
        return {
            'name': config['name'],
            'description': config['description'],
            'type': template_type
        }

class SlideLayouts:
    """Standard slide layout configurations."""
    
    LAYOUT_CONFIGS = {
        'title_slide': {
            'title_position': {'left': 0.5, 'top': 2.0, 'width': 9.0, 'height': 2.0},
            'subtitle_position': {'left': 0.5, 'top': 4.5, 'width': 9.0, 'height': 1.0}
        },
        'content_slide': {
            'title_position': {'left': 0.5, 'top': 0.5, 'width': 9.0, 'height': 1.0},
            'content_position': {'left': 0.5, 'top': 1.8, 'width': 9.0, 'height': 5.0}
        },
        'two_column_slide': {
            'title_position': {'left': 0.5, 'top': 0.5, 'width': 9.0, 'height': 1.0},
            'left_content_position': {'left': 0.5, 'top': 1.8, 'width': 4.25, 'height': 5.0},
            'right_content_position': {'left': 5.25, 'top': 1.8, 'width': 4.25, 'height': 5.0}
        },
        'use_case_slide': {
            'title_position': {'left': 0.5, 'top': 0.5, 'width': 9.0, 'height': 1.0},
            'problem_position': {'left': 0.5, 'top': 1.8, 'width': 9.0, 'height': 1.5},
            'solution_position': {'left': 0.5, 'top': 3.5, 'width': 9.0, 'height': 1.5},
            'benefits_position': {'left': 0.5, 'top': 5.2, 'width': 9.0, 'height': 1.5}
        }
    }
    
    @classmethod
    def get_layout_config(cls, layout_type: str) -> Dict[str, Dict[str, float]]:
        """Get layout configuration by type."""
        return cls.LAYOUT_CONFIGS.get(layout_type, cls.LAYOUT_CONFIGS['content_slide'])