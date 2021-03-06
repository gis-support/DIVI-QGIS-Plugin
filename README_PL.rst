========================
|logo| DIVI QGIS Plugin
========================

OPIS
++++

DIVI QGIS Plugin jest wtyczką do aplikacji QGIS, która służy do zarządzania danymi w systemie `DIVI <http://divi.pl>`_ firmy GIS Support sp. z o. o. Pozwala ona na przeglądać i edytować dane przestrzenne bezpośrednio w QGIS.
Aktualnie DIVI QGIS Plugin znajduje się w fazie beta.

Wtyczka została stworzona przez `GIS Support sp. z o. o. <http://www.gis-support.pl>`_

MOŻLIWOŚCI
++++++++++

- Wyświetlanie dostępnych kont, projektów oraz warstw i tabel w formie listy.
- Dodawanie warstw i tabel DIVI do QGIS, każdy typ geometrii warstw (punkt, linia, poligon) wczytywany jest jako osobna warstwa.
- Wymuszenie załadowania warstwy DIVI dla danego typu geometrii.
- Wczytanie wszystkich warstw z danego projektu.
- Edycja danych przestrzennych: dodawanie/usuwanie obiektów, edycja geometrii i atrybutów, dodawanie/usuwanie pól w tabeli atrybutów. Edycja odbywa się standardowymi narzędziami GIS.
- Zmiana nazwy warstwy/tabeli DIVI.
- Tworzenie nowych warstw DIVI poprzez przesłanie warstw QGIS.
- Odświeżenie wczytanych danych poprzez ponowne ich pobranie z systemu DIVI.

LINKI
+++++

- `Kod źródłowy <https://github.com/gis-support/DIVI-QGIS-Plugin>`_
- `Zgłaszanie błędów <https://github.com/gis-support/DIVI-QGIS-Plugin/issues>`_
- `Strona DIVI <https://divi.pl>`_
- `Strona GIS Support <http://gis-support.pl>`_

INSTALACJA
++++++++++

Wtyczka DIVI QGIS Plugin dostępna jest w oficjalnym repozytorium QGIS. Wtyczka jest w fazie beta i oznaczona jako eksperymentalna. W związku z tym, aby ją wyświetlić na liście w ustawieniach należy zaznaczyć opcję *Pokazuj wtyczki eksperymentalne*.

LICENCJA
++++++++

DIVI QGIS Plugin jest darmowym oprogramowaniem udostępnianym na licencji GNU General Public License w wersji 2 lub nowszej (wg potrzeb). Aplikację można dowolnie rozprzestrzeniać oraz modyfikować zgodnie z zapisami licencji. Tekst licencji dostępny jest w pliku LICENSE załączonym do repozytorium wtyczki oraz pod adresami:

- GNU General Public License Version 2 - http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
- GNU General Public License Version 3 - http://www.gnu.org/licenses/gpl-3.0.txt

.. |logo| image:: ./images/icon.png
