# BLP2PNG

This is a python script for converting .blp files to .png files and vice-versa.


##    Key Improvements:                                                                                                     
                                                                       
1. BLP Format Reporting: When you convert a .blp file, it now detects and prints the underlying encoding (e.g., DXT, Palette, ARGB8888).
2. Format Selection: When converting a .png to .blp, you can now specify the target format by passing an ID as the second argument:
        • 2 (Default): ARGB8888 (Full quality)
        • 0: DXT1                                                
        • 1: DXT3                                       
        • 7: DXT5
        • Note: For DXT formats, the script defaults to ARGB8888 to ensure data integrity, as high-fidelity DXT encoding is complex.
                                                   
##    Usage Examples:                                                   
             
  Convert BLP to PNG (outputs detected format)
  
  `python3 blp2png.py image.blp`           
  
  Convert PNG to BLP (using default ARGB8888)
  
  `python3 blp2png.py image.png`                
  
  Convert PNG to BLP (specifying a specific format ID, e.g., DXT5)     
  
  `python3 blp2png.py image.png 7`                                                                                                                                                                                                                                         
 
