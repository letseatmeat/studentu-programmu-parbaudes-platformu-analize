# CodeGrade AutoTest scripts

Šajā failā apkopoti praktiskajā aprobācijā izmantotie CodeGrade AutoTest skripti.
Katrs bloks tika ievietots atsevišķā CodeGrade “Script” blokā, kas bija sasaistīts ar atbilstošu rubrikas kategoriju, izmantojot “Connect Rubric”.

## Compilation test

```bash
set -e
g++ -std=c++17 -O2 -o main main.cpp
echo "Compilation test OK"
```

## Command “a” test

```bash
set -e
tr -d '\r' < db.csv > db_clean.csv && mv db_clean.csv db.csv
g++ -std=c++17 -O2 -o main main.cpp
printf "a\nRiga\nKraslava\ne\n" | ./main > out.txt

grep -F "result:" out.txt
grep -F "Riga Kraslava Pr 15:00 11.00" out.txt
grep -F "Riga Kraslava Pr 18:00 11.00" out.txt
echo "Command a test OK"
```

## Command “b” test

```bash
set -e
tr -d '\r' < db.csv > db_clean.csv && mv db_clean.csv db.csv
g++ -std=c++17 -O2 -o main main.cpp
printf "b\nPt\ne\n" | ./main > out.txt

grep -F "result:" out.txt
grep -F "Riga Ventspils Pt 09:00 6.70" out.txt
grep -F "Liepaja Ventspils Pt 17:00 5.50" out.txt
echo "Command b test OK"
```

## Command “c” test

```bash
set -e
tr -d '\r' < db.csv > db_clean.csv && mv db_clean.csv db.csv
g++ -std=c++17 -O2 -o main main.cpp
printf "c\n5.90\ne\n" | ./main > out.txt

grep -F "result:" out.txt
grep -F "Kraslava Daugavpils Ot 10:00 3.00" out.txt
grep -F "Dagda Kraslava Ce 18:00 2.50" out.txt
grep -F "Liepaja Ventspils Pt 17:00 5.50" out.txt
echo "Command c test OK"
```

## Command “d” test

```bash
set -e
tr -d '\r' < db.csv > db_clean.csv && mv db_clean.csv db.csv
g++ -std=c++17 -O2 -o main main.cpp
printf "d\ne\n" | ./main > out.txt

grep -F "result:" out.txt
grep -F "Ventsplis,8.00,Liepaja,Sv,20:00" out.txt
grep -F "Dagda,Sv" out.txt
grep -F "Dagda,Kraslava,Ce,18:00,2.50,Sv" out.txt
echo "Command d test OK"
```
