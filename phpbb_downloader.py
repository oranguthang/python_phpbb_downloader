#!/usr/bin/env python
import bs4
import os
import re
import requests
import sys
import threading
from urllib.parse import parse_qs, urlparse

visited_links = []
downloaded_files = []
db_fname = ""
bl_fname = ""
downloadThreads = []  # a list of all the Thread objects
external_links = []
log_file = ""
logtext = ""

sys.setrecursionlimit(10000)


def myprint(text):
    global logtext, log_file
    print(text)
    logtext += text + "\n"
    if len(logtext) > 1000:
        log = open(log_file, "a")
        log.write(logtext)
        logtext = ""


def save_to_database(url):
    global db_fname
    dbfile = open(db_fname, "a")
    dbfile.write(url + "\n")


def save_broken_link(url):
    global bl_fname
    blfile = open(bl_fname, "a")
    blfile.write(url + "\n")


def clean_link(base, url):
    url = url.lstrip('.')
    if not (url.startswith("http://") or url.startswith("https://")):
        if url.startswith("/"):
            url = "http://" + base + url
        else:
            url = "http://" + url
    return url


def update_file_name(filename):
    # remove ASCII character codes from filename
    reg = re.compile(r'(%\d{0,2})')
    filename = reg.sub(r'_', filename)
    # if current url need to download, but file exists
    try:
        if os.path.isfile(filename):
            # rename it
            f_n, f_ext = os.path.splitext(filename)
            i = 1
            while os.path.isfile(f_n + "_({0})".format(str(i)) + f_ext):
                i = i + 1
            filename_new = f_n + "_({0})".format(str(i)) + f_ext
            myprint('Rename file "{0}" to "{1}"'.format(filename, filename_new))
            filename = filename_new
    except:
        myprint('Error! Cannot check filename "{0}"'.format(filename))
        filename = ""
    return filename


def download_if_not_ex(folder, filename, url, getfname=False):
    global downloaded_files
    flag = True

    # if current file is not exist, download it
    if not url in downloaded_files:
        downloaded_files.append(url)
        save_to_database(url)
        try:
            res = requests.get(url)
            res.raise_for_status()
            if getfname:
                disp = res.headers['content-disposition']
                fn = re.findall(r"filename\*=UTF-8''(.+)", disp)
                filename = filename + "_" + fn[0]
        except:
            myprint("Error! Cannot download file: " + url)
            flag = False

        if flag:
            filename = os.path.join(folder, filename)
            filename = update_file_name(filename)
            if filename != "":
                someFile = open(filename, 'wb')
                for chunk in res.iter_content(100000):
                    someFile.write(chunk)
                someFile.close()
            else:
                myprint("Error! Cannot save downloaded file: " + url)
                filename = "index.html#ERROR"

    return os.path.basename(filename)


def download_recursively(url, basepath, folder, fname):
    global visited_links, external_links
    visited_links.append(url)

    currlinks = {}
    myprint('Download page "{0}"...'.format(url))

    try:
        res = requests.get(url)
        res.raise_for_status()
    except:
        myprint("Error! Cannot open page: " + url)
        save_broken_link(url)
        return

    soup = bs4.BeautifulSoup(res.text, 'html5lib')

    # Download .css files to ./<netloc>
    for link in soup.find_all('link', href=True):
        tempUrl = clean_link(basepath, link['href'])
        parsedUrl = urlparse(tempUrl)

        if parsedUrl.path.endswith(".css") or parsedUrl.path.endswith("style.php"):
            if parsedUrl.path.endswith("style.php"):
                qr = parse_qs(parsedUrl.query, keep_blank_values=True)
                tempUrl = parsedUrl.scheme + "://" + parsedUrl.netloc + parsedUrl.path + "?"
                if 'id' in qr.keys():
                    tempUrl = tempUrl + 'id=' + ''.join(qr['id']) + '&'
                if 'lang' in qr.keys():
                    tempUrl = tempUrl + 'lang=' + ''.join(qr['lang']) + '&'
                tempUrl = tempUrl.rstrip('&')
                css_fname = "style.css"
            else:
                css_fname = os.path.basename(parsedUrl.path)

            css_fname = download_if_not_ex(folder, css_fname, tempUrl)
            link['href'] = "./" + css_fname
        else:
            link['href'] = "#"

    # Download .js files to ./<netloc>
    for script in soup.find_all('script', src=True):
        tempUrl = clean_link(basepath, script['src'])
        parsedUrl = urlparse(tempUrl)

        if parsedUrl.path.endswith(".js"):
            js_fname = os.path.basename(parsedUrl.path)
            js_fname = download_if_not_ex(folder, js_fname, tempUrl)
            script['src'] = "./" + js_fname
        else:
            script['src'] = "#"

    # Download image files in <img> tag to ./<netloc>
    for img in soup.find_all('img', src=True):
        tempUrl = clean_link(basepath, img['src'])
        parsedUrl = urlparse(tempUrl)

        getfname = False
        img_fname = os.path.basename(parsedUrl.path)
        qr = parse_qs(parsedUrl.query, keep_blank_values=True)
        new_url = parsedUrl.scheme + "://" + parsedUrl.netloc + parsedUrl.path + "?"
        if 'avatar' in qr.keys():
            img_fname = ''.join(qr['avatar'])
            new_url = new_url + 'avatar=' + img_fname + '&'
        if 'id' in qr.keys():
            img_fname = ''.join(qr['id'])
            new_url = new_url + 'id=' + img_fname + '&'
            getfname = True
        new_url = new_url.rstrip('&')
        new_url = new_url.rstrip('?')
        img_fname = download_if_not_ex(folder, img_fname, new_url, getfname)
        img['src'] = "./" + img_fname

    # Download links in <a> tag
    for a in soup.find_all('a', href=True):
        tempUrl = clean_link(basepath, a['href'])
        parsedUrl = urlparse(tempUrl)

        if (parsedUrl.path.endswith("viewforum.php") or parsedUrl.path.endswith("viewtopic.php")) \
                and parsedUrl.netloc == basepath.split('/')[0]:
            qr = parse_qs(parsedUrl.query, keep_blank_values=True)
            if 'f' in qr.keys() or 't' in qr.keys():
                if parsedUrl.path.endswith("viewtopic.php") and ('t' not in qr.keys()):
                    a['href'] = "#"
                    continue

                new_url = parsedUrl.scheme + "://" + parsedUrl.netloc + parsedUrl.path + "?"
                if 'f' in qr.keys() and ('t' not in qr.keys()):
                    new_url = new_url + 'f=' + ''.join(qr['f']) + '&'
                if 't' in qr.keys():
                    new_url = new_url + 't=' + ''.join(qr['t']) + '&'
                if 'start' in qr.keys():
                    if ''.join(qr['start']) != "0":
                        new_url = new_url + 'start=' + ''.join(qr['start']) + '&'
                new_url = new_url.rstrip('&')

                new_fname = os.path.basename(new_url)
                if parsedUrl.path == "":
                    new_fname = "index.html"
                reg = re.compile(r'([.?=&])')
                new_fname = reg.sub(r'_', new_fname)
                new_fname += '.html'

                a['href'] = "./" + new_fname

                if new_url not in visited_links:
                    currlinks[new_url] = new_fname
        elif parsedUrl.path.endswith("dl_file.php") and parsedUrl.netloc == basepath.split('/')[0]:
            # get attachment
            att_name = "some_file"
            qr = parse_qs(parsedUrl.query, keep_blank_values=True)
            new_url = parsedUrl.scheme + "://" + parsedUrl.netloc + parsedUrl.path + "?"
            if 'site' in qr.keys():
                new_url = new_url + 'site=' + ''.join(qr['site']) + '&'
            if 'file' in qr.keys():
                att_name = ''.join(qr['file'])
                new_url = new_url + 'file=' + att_name + '&'
            new_url = new_url.rstrip('&')
            att_name = download_if_not_ex(folder, att_name, new_url)
            a['href'] = "./" + att_name
        elif parsedUrl.path.endswith("file.php") and parsedUrl.netloc == basepath.split('/')[0]:
            # get attachment
            getfname = True
            att_name = ""
            qr = parse_qs(parsedUrl.query, keep_blank_values=True)
            new_url = parsedUrl.scheme + "://" + parsedUrl.netloc + parsedUrl.path + "?"
            if 'id' in qr.keys():
                att_name = ''.join(qr['id'])
                new_url = new_url + 'id=' + att_name
            att_name = download_if_not_ex(folder, att_name, new_url, getfname)
            a['href'] = "./" + att_name
        elif parsedUrl.netloc == basepath.split('/')[0]:
            if parsedUrl.path.endswith("index.php"):
                a['href'] = "./index.html"
            else:
                a['href'] = "#"
        else:
            if parsedUrl.netloc != "":
                if tempUrl not in external_links:
                    external_links.append(tempUrl)
                    myprint("External link is found: " + tempUrl)

    # Save main file with BeautifulSoup rewrites
    temp_fname = ""
    try:
        temp_fname = os.path.join(folder, os.path.basename(fname))
        tempFile = open(temp_fname, 'wb')
        html = soup.prettify("utf-8")
        tempFile.write(html)
        tempFile.close()
    except:
        myprint('Error! Cannot save file from url "{0}" with name "{1}"'.format(url, temp_fname))

    # Download other .html files from current page
    for k_url, v_name in currlinks.items():
        # Check visited urls again
        if k_url not in visited_links:
            download_recursively(k_url, basepath, folder, v_name)


def download_forum(url, numthreads):
    numthreads = int(numthreads)
    url = url.rstrip('/')
    urlpars = urlparse(url)
    fold = urlpars.netloc
    os.makedirs(fold, exist_ok=True)  # store files in ./<netloc>
    basepath = fold + urlpars.path

    fname = urlpars.path
    if urlpars.path == "":
        fname = 'index.html'
    elif not (urlpars.path.endswith(".php") or urlpars.path.endswith(".html")):
        fname = fname + ".html"

    for i in range(numthreads):
        downloadThread = threading.Thread(target=download_recursively,
                                          args=[url, basepath, fold, fname])
        downloadThreads.append(downloadThread)
        downloadThread.start()

    # Wait for all threads to end
    for downloadThread in downloadThreads:
        downloadThread.join()
    myprint('Done.')


if len(sys.argv) == 6:
    db_fname = sys.argv[3]
    log_file = sys.argv[4]
    bl_fname = sys.argv[5]

    if os.path.isfile(db_fname):
        db_file = open(db_fname, 'r')
        downloaded_files = db_file.read().splitlines()
        db_file.close()
    download_forum(sys.argv[1], sys.argv[2])
else:
    print('Usage: ./phpbb_downloader.py <url> <number_of_threads> <db_name> <log_name> <file_with_broken_links>')
    print('Example: ./phpbb_downloader.py http://www.bokt.nl/forums/ 10 database.txt log.txt errorlinks.txt')
