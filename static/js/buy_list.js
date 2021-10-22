function myfunction(ele) {
    var loc = "http://localhost:5000/buy_one/" + ele;
    window.location.replace(loc);
}

function pay_now(ele) {
    var price = document.getElementById("godd2").innerHTML;
    var send = ele + '-' + price;
    var loc = "http://localhost:5000/buy_one/" + send + "/success";
    window.location.replace(loc);
}

function BuyOneUpdateFunction_Fast(bp) {
    document.getElementById("godd1").innerHTML = "Total (Book price + 2.5 %)";
    var oldprice = parseInt(bp);
    document.getElementById("godd2").innerHTML = (oldprice + (2.5 * oldprice) / 100).toFixed(4).toString();
}

function BuyOneUpdateFunction_Slow(bp) {
    document.getElementById("godd1").innerHTML = "Total (Book price + 1.5 %)";
    var oldprice = parseInt(bp);
    document.getElementById("godd2").innerHTML = (oldprice + (1.5 * oldprice) / 100).toFixed(4).toString();
}

function ListNewFast() {
    document.getElementById("ln1").innerHTML = "Total Mint Fee (2.5 % of set book price)";
    document.getElementById("ln2").innerHTML = ((2.5 / 100) * parseInt(document.getElementById("setted_price").value)).toFixed(4).toString();

}


function ListNewSlow() {
    document.getElementById("ln1").innerHTML = "Total Mint Fee (1.5 % of set book price)";
    document.getElementById("ln2").innerHTML = ((1.5 / 100) * parseInt(document.getElementById("setted_price").value)).toFixed(4).toString();

}