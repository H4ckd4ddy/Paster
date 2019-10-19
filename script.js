var delay_options = {
	'1-hour': {'text':'1 hour', 'seconds': (60*60), 'selected': true},
	'1-day': {'text':'1 day', 'seconds': (60*60*24), 'selected': false},
	'1-week': {'text':'1 week', 'seconds': (60*60*24*7), 'selected': false},
	'1-month': {'text':'1 month', 'seconds': (60*60*24*30), 'selected': false},
};
var destruction_option = {
	'text': 'self-destruct',
	'selected': false
};

function change_delay(new_delay){
	if(delay_options.hasOwnProperty(new_delay)){
		for(let [option, value] of Object.entries(delay_options)){
			if(option == new_delay){
				delay_options[option].selected = true;
			}else{
				delay_options[option].selected = false;
			}
		}
	}
	for(let [option, value] of Object.entries(delay_options)){
		let cross = (value.selected ? '<span style="color:#009900;">x</span>' : ' ');
		document.getElementById(option).innerHTML = '['+cross+'] '+value.text;
	}
}

function toggle_destruction(){
	destruction_option.selected = (destruction_option.selected?false:true);
	let cross = (destruction_option.selected ? '<span style="color:#009900;">x</span>' : ' ');
	document.getElementById('self-destruct').innerHTML = '['+cross+'] self-destruct';
}

function init_options(){
	for(let [option, value] of Object.entries(delay_options)){
		document.getElementById(option).addEventListener('click', function(){
			change_delay(this.id);
		}, false);
	}
	document.getElementById('self-destruct').addEventListener('click', function(){
		toggle_destruction();
	}, false);
	change_delay('1-hour');
}

function send_data(data, callback, key){
	var xhr = null; 
	if(window.XMLHttpRequest){ // Firefox et autres
		xhr = new XMLHttpRequest(); 
	}else if(window.ActiveXObject){ // Internet Explorer 
		try {
			xhr = new ActiveXObject('Msxml2.XMLHTTP');
		} catch (e) {
			xhr = new ActiveXObject('Microsoft.XMLHTTP');
		}
	}else{
		alert('Votre navigateur ne supporte pas les objets XMLHTTPRequest...'); 
		xhr = false; 
	}
	xhr.onreadystatechange = function(){
		if( xhr.readyState < 4 ){
			//loading
		}else if(xhr.readyState == 4 && xhr.status == 200){
			//end loading
			callback(xhr.responseText, key);
		}else if(xhr.readyState == 4 && xhr.status != 200){
			//end loading
			callback(xhr.responseText, key, true);
		}
	}
	xhr.open('POST', '/', true);
	xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
	xhr.send(data);
}

function buf2hex(buffer){
	return Array.prototype.map.call(new Uint8Array(buffer), x => ('00' + x.toString(16)).slice(-2)).join('');
}

function hex2buf(string) {
	return new Uint8Array(string.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
}

function str2buf(string){
	var bytes = new Uint8Array(string.length);
	for (var i = 0; i < string.length; i++){
		bytes[i] = string.charCodeAt(i);
	}
	return bytes;
}

function buf2str(buffer){
	var str = "";
	for (var i = 0; i < buffer.byteLength; i++){
		str += String.fromCharCode(buffer[i]);
	}
	return str;
}

function sha256(message){
	var encoder = new TextEncoder()
	return window.crypto.subtle.digest(
		{
			name: "SHA-256",
		},
		new Uint8Array(encoder.encode(message))
	).then(function(hash){
		return buf2hex(hash);
	}).catch(function(err){
		console.error(err);
	});
}

function aes256_import_key(hex_key){
	return window.crypto.subtle.importKey(
		"raw",
		hex2buf(hex_key).buffer,
		{
			name: "AES-CBC",
			length: 256,
		},
		false,
		["encrypt", "decrypt"]
	).then(function(key){
		return key;
	})
}

function aes256_encrypt(key, string_data){
	var iv = window.crypto.getRandomValues(new Uint8Array(16));
	return window.crypto.subtle.encrypt(
		{
			name: "AES-CBC",
			iv: iv,
		},
		key,
		str2buf(string_data)
	)
	.then(function(encrypted){
		return Promise.resolve({
			"cipher": buf2hex(encrypted),
			"iv": buf2hex(iv)
		})
	})
	.catch(function(err){
		console.error(err);
	});
}

function aes256_decrypt(key, hex_iv, hex_data){
	return window.crypto.subtle.decrypt(
		{
			name: "AES-CBC",
			iv: hex2buf(hex_iv),
		},
		key,
		hex2buf(hex_data)
	)
	.then(function(decrypted){
		return buf2str(new Uint8Array(decrypted));
	})
	.catch(function(err){
		console.error(err);
	});
}

function get_delay(){
	var delay;
	for(let [option, value] of Object.entries(delay_options)){
		if(value.selected){
			delay = value.seconds;
		}
	}
	return delay;
}

async function submit_text(){
	var text = document.getElementById('input').value;
	var key = buf2hex(window.crypto.getRandomValues(new Uint8Array(16)));
	var text_id = await sha256(key)
							.then(hash => sha256(hash))
							.then(hash => sha256(hash))
							.then(hash => sha256(hash));
	
	var aes_key = await sha256(key);
	
	var encrypted_text = await aes256_import_key(aes_key).then(key => aes256_encrypt(key, text));

	if(destruction_option.selected){
		encrypted_text.options = ["self-destruct"];
	}

	encrypted_text.deletion = Math.round((Date.now()/1000) + get_delay());

	var data = 'text_id='+text_id+"&encrypted_text="+JSON.stringify(encrypted_text);
	send_data(data, show_link, key);
}

function show_link(response, key, error=false){
	document.getElementById('home').style.display = 'none';
	document.getElementById('show_result').style.display = 'block';
	if(!error){
		var result = JSON.parse(response);
		if(result["state"] == "OK"){
			document.getElementById("result").innerHTML = "Your link : <br/><br/>" + url + '/#' + key;
			return;
		}
	}
	document.getElementById("result").innerHTML = '<span class="error">' + response + '</span>';
}

async function get_text(){
	var key = window.location.hash.split('?')[0].split('&')[0].replace('#', '')
	var text_id = await sha256(key)
					.then(hash => sha256(hash))
					.then(hash => sha256(hash))
					.then(hash => sha256(hash));
	var aes_key = await sha256(key);
	var data = 'text_id='+text_id;
	send_data(data, show_text, key);
}

async function show_text(response, key, error=false){
	try {
		if(error){
			throw 'HTTP error';
		}
		var result = JSON.parse(response);
		if(result["state"] != "OK"){
			throw 'State error';
		}else{
			var encrypted_text = JSON.parse(result["encrypted_text"]);
			var aes_key = await sha256(key);
			var decrypted_text = await aes256_import_key(aes_key).then(key => aes256_decrypt(key, encrypted_text.iv, encrypted_text.cipher));
			document.getElementById('text').value = decrypted_text;
		}
	} catch(error) {
		document.getElementById("result").innerHTML = '<span class="error">' + response + '</span>';
		document.getElementById('show_text').style.display = 'none';
		document.getElementById('show_result').style.display = 'block';
	}
}

document.addEventListener("DOMContentLoaded", function() {
	if(window.location.hash.length > 0){
		get_text();
		document.getElementById('show_text').style.display = 'block';
	}else{
		init_options();
		document.getElementById('home').style.display = 'block';
	}
});