https://foro.ignetwork.net/showthread.php?49658-Guia-upload-via-fetch!


Guia upload via fetch!
Holas Amigos aqui esta el aporte 100% entendible para la gente quedesea actualizar su servidor via fetch.

Primero descargar lo siguiente!

Download fetchIG.rar from Sendspace.com - send big files the easy way

consta de 4 phps, 1 INI, 1 IXFS y el upload.xfs

una vez descargado descomprimalo y pegelo en la ruta de su web osea

C:\AppServ\www\ en mi caso.




AHORA ABRIMOS LA CARPETA "fetchIG" y abrimos "602.ini"

encontraremos de la siguiente manera

```
+http://gb-american.servegame.com/fetch/
=http://gb-american.servegame.com/fetch/
~1;14565;602
M;.\graphics.xfs;602/avatar.xfs;602;14565
```

la linea "+http://gb-american.servegame.com/fetch/" tiene que ser cambiada por nuestra ruta en el caso seria

+404 Not Found

ahora en la otra linea

```
"=http://gb-american.servegame.com/fetch/
~1;14565;602
"
```
preste mucha antecion!!

editemos hasta la ruta

```
=http://localhost/fetchIG/
~1;14565;602
```

ahora la linea que quedo `~1;14565;602` es lo que se pondra depende al peso del xfs y la version de su cliente.
separemos las lineas

`~1` -> Cantidad de archivos puestos en el xfs.<br>
`14565` -> Peso de Archivo .xfs<br>
`602` -> version del cliente +1


AHORA!! para poder hacer esto con exito necesitamos saber la version de nuestro cliente...

abrimos el IXFS y abriremos el graphics de nuestro cliente



en mi caso la version de mi cliente es 601 como ven en la foto de arriba :biggrin:



Ahora como ya tenemos la version tenemos que poner la version superior que sera, ejemplo.
si mi version es 601 el actu que colocare debe ser version 602 ( +1 version )

abrimos el IXFS y vamos a nuestra carpeta de actualizacion!

`C:\AppServ\www\fetchIG\files`

y abrimos el upload.xfs





LA VERSION ES 602 Ese .xfs que actualiza siempre debe ir una version +1 que su xfs
EJEMPLO:

LA VERSION ES 601 ENTONCES DEBEMOS COLOCAR 602 AL upload.xfs

Una vez visto la version +1 al `upload.xfs` pondremos en "Adaptar Archivo" encaso que su version sea otra siempre sumelo +1 al .xfs que actualizara.


RECORDEMOS QUE NOS QUEDAMOS EN ESTA LINEA

```
~1                    -> Cantidad de archivos puestos en el xfs.
14565        -> Peso de Archivo .xfs
602                  -> version del cliente +1
```

donde dice "14565" es el peso del archivo en bites.. poes hacemos lo siguiente...

CLICK DERECHO AL UPLOAD.XFS Y VAMOS A PROPIEDADES
Y COPIAREMOS EL PESO DEL ARCHIVO




EN ESE CASO ES 14.565 AHORA LE QUITAREMOS EL "." Y QUEDARA 14565 ASI ES COMO QUEDA EN EL .INI


EN RESUMEN TODO NUESTRO 602.INI ESTARIA ASI

```
=http://localhost/fetchIG/
~1;14565;602
M;.\graphics.xfs;602/upload.xfs;602;14565
```

LOS QUE ESTAN DE COLOR MORADO: DESCRIBEN EL PESO DEL ARCHIVO EN BITS QUITANDOLE EL "."
LOS QUE ESTAN EN COLOR ROJO: DESCRIBEN LA VERSION +1 DE SU CLIENTE
LOS QUE ESTAN DE AZUL: DESCRIBE LA UBICACION DE LA CARPETA CON EL ARCHIVO UPLOAD.XFS
LOS QUE ESTAN DE NARANJA: DESCRIBE LA CANTINDAD DE ARCHIVOS PUESTOS EN EL .XFS
LOS QUE ESTAN EN VERDE: DESCRIBE AL GRAPHICS.XFS = M // AVATAR.XFS = R
M;.\graphics.xfs <--- EN ESTE CASO ES PARA ACTUALIZAR EL GRAPHICS.XFS
R;.\avatar.xfs <--- EN ESTE OTRO ES PARA ACTUALIZAR EL AVATAR.XFS


AHORA SI, EN CASO QUE SEA OTRA VERSION EJEMPLO : 140
ENTRA AL FETCH.PHP

Código PHP:
```php
<?php
if (isset($_GET['604'])) {   // EL 604 EXPRESA EL APPID GENERALIZADO ESTO DEJALO COMO ESTA.
    include "602.ini";       //   DICE LA VERSION LA PUEDES CAMBIAR +1 "141"  Y TAMBIEN ES EL CONFIG DEL UPLOAD. ( NO BORRAR EL .INI)
} else {

}
```

Esto implica en cambiarle la version al upload.xfs / y editas las lineas como expresa en la parte superior.

AHORA POR ULTIMO EDITAREMOS EL INI LANCHERD DE NUESTRO CLIENTE

EN MI CASO ES ASI

```ini
[GbPeru]
Url_Fetch=http://127.0.0.1/fetch/fetch.php
Url_ForgotPwd=http://www.gunbound-peru.com/?mod=3&op=opass
Url_Signup=http://www.gunbound-peru.com/?mod=3&op=register
Url_FindId=http://www.gunbound-peru.com
Url_Softnyx=http://www.gunbound-peru.com
Url_Ad=http://www.gunbound-peru.com
Ip=127.0.0.1
Port=8372
AppId=400
Version=605
CookieDomain=http://softnyx.net/
CookieName=Softnyx_Eng
LastGame=Gunbound
[Gunbound]
AppId=2101
Url_Notice=http://www.gunbound-peru.net/noticia/index.html
Url_ManualPatch=http://gbmundial.net/descargas.asp
Url_FullDownload=http://www.gunbound-peru.com/index.asp?op=descargas
Url_Fetch=http://127.0.0.1/fetch/fetch.php
```

LOS QUE ESTAN DE NARANJA ACUERDATE QUE TIENE QUE SEÑALAR AL FETCH QUE NOSOTROS EDITAMOS CAMBIENLO POR EL :


AHORA SI ABRAN SU GB Y VERAN QUE COMIENZA A CARGAR :icon_lol:





LUEGO ABREN SU IXFS Y ABREN SU GRAPHICS Y SE DARAN CUENTA QUE SE ADELANTO UNA VERSION MAS ... LISTO ;D


CREDITOS TEAM SERVICE