A=0
for i in `ls pics-ballona`
do
  A=`echo "$A+1" | bc`
  echo "<div class=\"mySlides fade\"> <div class=\"numbertext\">$A / 86</div> <img src=\"pics-ballona/"$i"\" style=\"width:100%\"> </div>"
done
