DPATH=~/.local/share/applications/
IPATH=~/.local/share/icons/hicolor/scalable/apps/
PPATH="/usr/local/bin/"
mkdir -p $DPATH $IPATH $PPATH
cp ./assets/otrimmer.desktop $DPATH
cp ./assets/otrimmer.svg $IPATH
sudo cp ./otrimmer.bin $PPATH/otrimmer
sudo cp ./assets/otrimmer-launcher.sh $PPATH/otrimmer-launcher