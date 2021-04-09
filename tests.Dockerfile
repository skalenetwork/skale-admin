FROM admin:base

RUN pip3 install --no-cache-dir -r requirements-dev.txt

RUN pip3 uninstall pycrypto -y
RUN pip3 uninstall pycryptodome -y
RUN pip3 install pycryptodome
