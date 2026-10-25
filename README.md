# BLP2PNG

This is a python script for converting .blp files to .png files and vice-versa.


                                                  
##    Usage Examples:                                                   
             
  Convert BLP to PNG
  
  `python3 BLPNG.py image.blp`           
  
  Convert PNG to BLP
  
  `python3 BLPNG.py image.png`                
  
  Convert multiple files at once

  `for file in /path/to/files/*.blp; do python BLPNG.py "$file"; done`
  `for file in /path/to/files/*.png; do python BLPNG.py "$file"; done`

  Convert multiple nested folders

  `find /pathe/to/folders -type f -name "*.blp" -exec python BLPNG.py {} \;`
  `find /pathe/to/folders -type f -name "*.png" -exec python BLPNG.py {} \;`

  
