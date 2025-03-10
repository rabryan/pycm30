#ZS="2487.5 2489.0625 2490.625 2492.1875 2493.75 2495.3125 2496.875 2498.4375 2500.0 2501.5625 2503.125 2504.6875 2506.25 2507.8125 2509.375 2510.9375 2512.5 2514.0625 2515.625 2517.1875 2518.75 2520.3125 2521.875 2523.4375 2525.0 2526.5625 2528.125 2529.6875 2531.25 2532.8125 2534.375 2535.9375 2537.5 2539.0625"
ZS="2501.5625 2503.125 2504.6875 2506.25 2507.8125 2509.375 2510.9375 2512.5 2514.0625 2515.625 2517.1875 2518.75 2520.3125 2521.875 2523.4375 2525.0 2526.5625 2528.125 2529.6875 2531.25 2532.8125 2534.375 2535.9375 2537.5 2539.0625"
YMAX=45000
YMIN=35000
XMAX=58000
XMIN=48000
SS=50
ISO=100
for z in $ZS; do
    for ss in "20 30 40 50 60 80 100"; do
        TAG=z_eval_red_dark_$z_ss_$ss
        DIR=~/Documents/lucid/experiments/cm30/calibration-slide/$TAG
        mkdir $DIR
        python3 pycm30/cli.py scan-area $XMIN $XMAX $YMIN $YMAX $DIR --hostname lucid-hub-acym --autofocus-init False --fixed-z $z --autofocus-all False --iso $ISO --shutter-speed-denominator $ss
        python3 tile.py $DIR
        cp /home/rabryan/.tmp/tiled.jpg ~/Pictures/ref-slide-$TAG.jpg
done
