"""
Windows DWM Effects Module

Provides native Windows 10/11 blur effects using the Desktop Window Manager API.
Falls back gracefully on unsupported platforms.
"""
import ctypes
from ctypes import c_int, byref, Structure, POINTER
import logging

logger = logging.getLogger(__name__)


class WindowEffect:
    """Enables Windows 11 Acrylic Blur Effect using DWM API."""
    
    # Windows API Constants
    ACCENT_DISABLED = 0
    ACCENT_ENABLE_GRADIENT = 1
    ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
    ACCENT_ENABLE_BLURBEHIND = 3
    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
    
    # Window Composition Attribute
    WCA_ACCENT_POLICY = 19
    
    def __init__(self):
        self._is_windows = self._check_windows()
    
    def _check_windows(self) -> bool:
        """Check if running on Windows."""
        import sys
        return sys.platform == 'win32'
    
    def set_acrylic(self, hwnd, gradient_color: int = 0x99F2F2F2):
        """
        Apply acrylic blur effect to window.
        
        Args:
            hwnd: Window handle (from QWidget.winId())
            gradient_color: AABBGGRR format color (default: semi-transparent white)
        """
        if not self._is_windows:
            logger.debug("Acrylic blur not available on this platform")
            return False
        
        try:
            # Define structures
            class ACCENT_POLICY(Structure):
                _fields_ = [
                    ("AccentState", c_int),
                    ("AccentFlags", c_int),
                    ("GradientColor", c_int),
                    ("AnimationId", c_int)
                ]
            
            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [
                    ("Attribute", c_int),
                    ("Data", POINTER(ACCENT_POLICY)),
                    ("SizeOfData", c_int)
                ]
            
            # Create policy with acrylic blur
            # AccentFlags=2 is required for proper rendering on Windows 10/11
            policy = ACCENT_POLICY(
                self.ACCENT_ENABLE_ACRYLICBLURBEHIND,
                2,  # AccentFlags: 2 = Draw all present bits
                gradient_color,
                0
            )
            
            # Create composition data
            data = WINDOWCOMPOSITIONATTRIBDATA(
                self.WCA_ACCENT_POLICY,
                ctypes.pointer(policy),
                ctypes.sizeof(policy)
            )
            
            # Apply the effect
            result = ctypes.windll.user32.SetWindowCompositionAttribute(
                int(hwnd),
                byref(data)
            )
            
            if result:
                logger.info("Acrylic blur effect applied successfully")
                return True
            else:
                logger.warning("SetWindowCompositionAttribute returned 0")
                return False
                
        except AttributeError:
            logger.warning("SetWindowCompositionAttribute not available (older Windows version)")
            return False
        except Exception as e:
            logger.error(f"Failed to apply acrylic blur: {e}")
            return False
    
    def set_blur_behind(self, hwnd):
        """
        Apply standard blur behind effect (Windows 10 compatible).
        Fallback for systems that don't support acrylic.
        """
        if not self._is_windows:
            return False
        
        try:
            class ACCENT_POLICY(Structure):
                _fields_ = [
                    ("AccentState", c_int),
                    ("AccentFlags", c_int),
                    ("GradientColor", c_int),
                    ("AnimationId", c_int)
                ]
            
            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [
                    ("Attribute", c_int),
                    ("Data", POINTER(ACCENT_POLICY)),
                    ("SizeOfData", c_int)
                ]
            
            policy = ACCENT_POLICY(self.ACCENT_ENABLE_BLURBEHIND, 0, 0, 0)
            data = WINDOWCOMPOSITIONATTRIBDATA(
                self.WCA_ACCENT_POLICY,
                ctypes.pointer(policy),
                ctypes.sizeof(policy)
            )
            
            result = ctypes.windll.user32.SetWindowCompositionAttribute(
                int(hwnd),
                byref(data)
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to apply blur behind: {e}")
            return False
