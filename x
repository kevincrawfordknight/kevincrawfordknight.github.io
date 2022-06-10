A=0
for i in `ls pics-cooking`
do
  A=`echo "$A+1" | bc`
  echo "<div class=\"mySlides fade\"> <div class=\"numbertext\">$A / 86</div> <img src=\"pics-cooking/"$i"\" style=\"width:100%\"> </div>"
done
