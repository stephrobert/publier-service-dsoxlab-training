# Scénario

La machine porte un Nginx installé par le paquet de la distribution, et rien
d'autre : le site de démonstration a été retiré, aucun service n'est publié,
et le service est **arrêté et non activé au démarrage**.

Le backend à publier écoute déjà sur `127.0.0.1:18092`. Ce que
l'installation doit présenter est écrit dans
`/opt/pub-nginx-installation/manifeste.txt`.

## Mission

Publiez `app.lab.test` vers le backend, en suivant le manifeste. Montrez
ensuite que vous savez distinguer les trois gestes qu'on confond le plus
souvent : valider, recharger, redémarrer.

## Les quatre contrôles, et pourquoi le dernier décide

1. **Ce qui tourne suit le manifeste.** La version lue sur le binaire est
   comparée à celle que le manifeste annonce, et non à une valeur écrite en
   dur dans le test : un test qui affirmerait « 1.24 » deviendrait faux le
   jour où la distribution bouge, sans qu'on puisse dire qui a tort.

2. **Une directive mal placée est refusée**, et le service tient. Les deux
   moitiés comptent : refuser une configuration fautive ne vaut rien si le
   service tombe en même temps, et c'est exactement ce que produit un
   `restart` lancé sans validation préalable.

3. **Un changement valide s'applique sans remplacer le processus maître.**
   Le test compare le PID avant et après : c'est ce qui distingue un reload
   d'un restart, et la distinction n'est pas théorique, puisqu'un restart
   coupe les connexions en cours.

4. **Le service revient après un redémarrage de la machine.** C'est le
   contrôle qui décide : un service qui répond aujourd'hui et ne revient pas
   demain n'est pas installé, il est lancé. La différence ne se voit qu'en
   redémarrant pour de bon, et le test le fait.

Ce dernier test coupe la machine. Il est donc joué en dernier : tout ce qui
le suivrait mesurerait un autre état.
