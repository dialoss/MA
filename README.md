Test task solution. 4lapy mobile app parser
# Steps done for achieving result:
## SSL unpunnnig of the app:
+ Decompile apk
+ Change network security config
+ Compile and Sign apk
+ Install frida server on emulator
+ Install apk
+ Install custom network certificate
+ Run frida on desktop for ssl decryption of requests
## Reverse-engineering sign function of the request:
+ The function was found in q.class file
+ It's simply "ABCDEF00G" + sorted hashed parameters
+ Hash function is MD5
## Endpoints used
+ https://4lapy.ru/api/v2/catalog/product/list/
+ https://4lapy.ru/api/v2/catalog/product/info-list/
