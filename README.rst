========================
|logo| DIVI QGIS Plugin
========================

OPIS
++++

DIVI QGIS Plugin jest wtyczką do aplikacji QGIS, która służy do zarządzania danymi w systemie DIVI firmy GIS Support sp. z o. o. Pozwala ona na przeglądać i edytować dane przestrzenne bezpośrednio w QGIS.
Aktualnie DIVI QGIS Plugin znajduje się w fazie beta.

Wtyczka została stworzona przez `GIS Support sp. z o. o. <http://www.gis-support.pl>`_


INSTALACJA
++++++++++

Wtyczka DIVI QGIS Plugin dostępna jest w repozytorium GIS Support. Aby dodać repozytorium do listy należy:

1) W menu *Wtyczki* wybrać pozycję *Zarządzaj wtyczkami...*;
2) Przejść na zakładkę *Ustawienia*;
3) Kliknąć przycisk *Dodaj...*;
4) W oknie dialogowym wpisać nazwę (może być dowolna np. GIS Support) i URL do repozytorium: https://plugins.gis-support.pl/plugins.xml i kliknąć *OK*;

Wtyczka jest w fazie beta. W związku z tym, aby ją wyświetlić na liście wtyczke należy zaznaczyć opcję *Pokazuj wtyczki eksperymentalne*.


MOŻLIWOŚCI
++++++++++

- Wyświetlanie dostępnych kont, projektów oraz warstw i tabel w formie listy.
- Dodawanie warstw DIVI do QGIS, każdy typ geometrii (punkt, linia, poligon) wczytywany jest jako osobna warstwa.
- Wymuszenie załadowania warstwy DIVI dla danego typu geometrii.
- Edycja danych przestrzennych: dodawanie/usuwanie obiektów, edycja geomtrii i atrybutów, dodawanie/usuwanie pól w tabeli atrybutów. Edycja odbywa się standardowymi narzędziami GIS.
- Odświeżenie wczytanych danych poprzez ponowne ich pobranie z systemu DIVI.


LICENCJA
++++++++

DIVI QGIS Plugin jest darmowym oprogramowaniem udostępnianym na licencji GNU General Public License w wersji 2 lub nowszej (wg potrzeb). Aplikację można dowolnie rozprzestrzeniać oraz modyfikować zgodnie z zapisami licencji. Tekst licencji dostępny jest w pliku LICENSE załączonym do repozytorium wtyczki oraz pod adresami:

- GNU General Public License Version 2 - http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
- GNU General Public License Version 3 - http://www.gnu.org/licenses/gpl-3.0.txt

.. |logo| image:: ./images/icon.png