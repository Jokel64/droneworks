$nodes_to_start = 10

$i = 1
While($i -lt $nodes_to_start) {

Start-Process python .\main.py

Start-Sleep -Seconds 2

$i++}