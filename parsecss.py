#!/usr/bin/env python

import sys, os, requests
from urllib.parse import urlparse

if len(sys.argv) == 3:
    fname = sys.argv[1]
    url = sys.argv[2]
    url = url.rstrip("/")
    
    if os.path.isfile(fname):
        links_file = open(fname, 'r')
        links = links_file.read().splitlines()
        links_file.close()
        
        for p in links:
            if p == "":
                continue
            
            p = p.lstrip(".")
            lnk = url + p
            
            print('Download file "' + lnk + '"...')
            try:
                res = requests.get(lnk)
                res.raise_for_status()
            except Exception as e:
                print("Error! Cannot download file: " + lnk)
                print(str(e))
                
            try:
                dirpath = os.path.dirname(p)
                dirpath = dirpath.strip("/")
                os.makedirs(dirpath, exist_ok=True)
            except Exception as e:
                print("Error! Cannot create path: " + dirpath)
                print(str(e))
                
            try:
                pars = urlparse(lnk)
                path = pars.path.lstrip("/")
                finalPath = os.path.join(path)
                tempFile = open(finalPath, 'wb')
                for chunk in res.iter_content(100000):
                    tempFile.write(chunk)
                tempFile.close()
            except Exception as e:
                print("Error! Cannot save file from url: " + lnk)
                print(str(e))
