let debug = 0
debug && console.log('debug mode ON')

// lottery-play conversion
const lotteryPlayClick = () => {
	if (location.hostname.includes('tenki-japan')) {
		gtag('event', 'conversion', {'send_to': 'AW-831208458/y9YdCN7X-OsZEIr4rIwD'})
	}
	const page_location = `${location.pathname}/lottery-play`.replace('//', '/')
	gtag('set', 'page', page_location)
	gtag('send', 'pageview', page_location)
	gtag('send', 'page_view', {page_location})
  }

//   lottery-coupon-get conversion
const lotteryCouponGetClick = shop_id_url => {
	if (location.hostname.includes('tenki-japan')) {
		gtag('event', 'conversion', {'send_to': 'AW-831208458/DlQuCOHX-OsZEIr4rIwD'})
	}
	const page_location = `${location.pathname}/lottery-coupon-get/${shop_id_url}`.replace('//', '/')
	gtag('set', 'page', page_location)
	gtag('send', 'pageview', page_location)
	gtag('send', 'page_view', {page_location})
  }

let currShopId = location.href.split('/')[4]
if (!location.hostname || location.hostname.includes('tenki-japan')) {
	currShopId = undefined
}

let dataReadyCallabck
let weightedShopsPromise = new Promise(r => dataReadyCallabck = r)
if (debug) {
	fetch('https://data.tenki-japan.co.jp/rakuten.ne.jp/traffic-exchange-data.json')
		.then(r => r.json())
		.then(data => {
			dataReadyCallabck(data.shops.filter(s => s.weight && s.coupons && s.coupons.length))
		})
} else {
	addEventListener('message', ({data}) => {
		console.log({data})
		dataReadyCallabck(data.shops.filter(s => s.weight && s.coupons && s.coupons.length))
	})
}

const rand = (min, max) => Math.floor(Math.random()*(max-min+1)+min)
let images = []
const SLOTS_PER_REEL = 12
const REEL_RADIUS = 150
const createSlots = (ring) => {
	var slotAngle = 360 / SLOTS_PER_REEL;
	var seed = 0;
	for (var i = 0; SLOTS_PER_REEL > i; i ++) {
		var slot = document.createElement('div');
		slot.className = 'slot';
		var transform = 'rotateX(' + (slotAngle * i) + 'deg) translateZ(' + REEL_RADIUS + 'px)';
		slot.style.transform = transform;
		var content = slot.innerHTML = `<p style="background-image: url(${images[i]}?fitin=180:180)"></p>`
		ring.append(slot)
	}
}
let rate = 80
let luck = rand(1, 100)
let winIndex
const spin = () => {
	let num = undefined
	if (luck <= rate) {
		num = winIndex
		for (var i = 2; 5 > i; i ++) {
			document.querySelector('#ring'+i).style.animation = `back-spin 1s, spin-${num} ${(1 + i*1)}s`
			document.querySelector('#ring'+i).setAttribute('class','ring spin-' + num)
		}
	} else {
		for (var i = 2; 5 > i; i ++) {
			const num = rand(1, SLOTS_PER_REEL)
			document.querySelector('#ring'+i).style.animation = `back-spin 1s, spin-${num} ${(1 + i*1)}s`
			document.querySelector('#ring'+i).setAttribute('class','ring spin-' + num)
		}
	}
	setTimeout(showResultMessage, 5200, num)
}

const showResultMessage = num => {
	if (num!==undefined) {
		displayWin()
	} else {
		displayLose()
	}
	document.querySelector('#rotate').classList.add('display-none')
	document.querySelector('#rotate').classList.add('low')
	document.querySelector('#final-message').classList.remove('display-none')
	disableAnimation()
}

const disableAnimation = () => {
	document.querySelectorAll('.ring').forEach(el => el.style.cssText = '')
}

const displayLose = () => {
	user.last_ts = +new Date
	localStorage.setItem('user', JSON.stringify(user))
	setTimeout(updateCountDown, 200)
	document.querySelector('#final-message').innerHTML = `<div id="center-container" style="position: fixed;top: 0;left: 0;width: 100%;height: 100%;display: flex;justify-content: center;align-items: center;background-color: rgba(0, 0, 0, 0.5);z-index: 9999;"><div style="width: 60%;background-color: rgba(0, 0, 0, 0.7);border: none;border-radius: 5px;padding: 20px 10px;font-size:1em;text-align: center;color: white;">残念！ハズレ！<br><span id="countdown"></span> 秒後にもう一度チャレンジしてみてね！</div></div>`
	disableAnimation()
}
const displayWin = () => {
	const shop = shops.find(s => s.shop_id===winShopId)
	const coupons = shop.coupons
	const coupon = coupons[rand(0, coupons.length-1)]
	user.last_ts = +new Date
	user.clist.push(coupon.cuid)
	localStorage.setItem('user', JSON.stringify(user))

	shop.items.forEach(i => {
	})
	setTimeout(updateCountDown, 200)
	document.querySelector('#final-message').innerHTML = `
		<div style='padding:20px 40px;text-align:left;'>
			<div style='background-color:rgba(0, 0, 0, 0.7);border:none;border-radius:5px;padding:3px 10px;font-size:1em;text-align:center;margin-bottom:20px;display:block'><span id="countdown"></span> 秒後にもう一度お試しください</div>
			<a onclick="lotteryCouponGetClick('${shop.shop_id}')" href="${coupon.url}" style="color:white;text-decoration:none" target="_blank">
				<div style='float:left;margin-bottom:10px'>
					<div style='float:left;width:10%'><img style="width:100%;" src="https://thumbnail.image.rakuten.co.jp/@0_mall/${shop.shop_id}/logo/logo1.jpg"></div>
					<div style='float:left;width:90%'><div style='padding-left:10px;font-size:1em;font-weight:bold;'>${(shop.tagline||"").replace(/<[^>]+>/g,"")}</div></div>
				</div>
				<div style='clear:both'></div>
				<div style='display:flex;flex-wrap:wrap; gap:0px;padding-top:10px'>
				${shop.items.slice(0, 4).map(i => {
					const url = `${coupon.url}`
					return `
						<div class="con_image">
							<a href="${url}" target="_blank"><img src="${i.images[0]}"></a>
						</div>`
				}).join('')}
				</div>
		
				<div style='color:white;padding-top:10px;font-size:0.8em'>
					${coupon.type==='percent'?`${coupon.amount}%`:`${coupon.amount}円`}OFF
				</div>
				
				<div style="color:white;font-size:0.8em;margin-bottom:3px;white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
					${coupon.title}
				</div>
				<a onclick="lotteryCouponGetClick('${shop.shop_id}')" href="${coupon.url}" style="color:white;text-decoration:none" target="_blank">
					<div style='float:left;width:100%;background:#faef7f;'>
						<div style="float:left;width:10%"><img src="slot_coupon_icon.png" style="padding:0 5px;width:60%;"></div>
						<div style="float:left;width:70%;padding-top:5px;font-size:0.8em;color:black;font-weight:bold">クーポンはこちら</div>
						<div style="float:left;width:19%;font-size:0.8em;color:black;text-align:right"><div style='padding-right:23px'>→</div></div>
					</div>
				</a>
			</a>
		</div>
	`
	disableAnimation()
}

const displayComeBackTomorrow = () => {
	document.querySelector('#final-message').classList.remove('display-none')
	document.querySelector('#final-message').innerHTML = `<div id="center-container" style="position: fixed;top: 0;left: 0;width: 100%;height: 100%;display: flex;justify-content: center;align-items: center;background-color: rgba(0, 0, 0, 0.5);z-index: 9999;"><div style="width: 60%;background-color: rgba(0, 0, 0, 0.7);border: none;border-radius: 5px;padding: 20px 10px;font-size:1em;text-align: center;color: white;">今日は抽選の回数を全部使い切っちゃった！<br>また明日チャレンジしてね！</div></div>`
	disableAnimation()
}
	const updateCountDown = () => {
	const secondsLeft = secondsBetweenPlay - Math.round((+new Date - user.last_ts) / 1_000)
	if (secondsLeft<0) {
		// refresh page
		location.href = location.href
	} else {
		document.querySelector('#countdown').textContent = secondsLeft
		setTimeout(updateCountDown, 200)
	}
}


const displayCanPlaySoon = () => {
	document.querySelector('#final-message').classList.remove('display-none')


	setTimeout(updateCountDown, 200)
	document.querySelector('#final-message').innerHTML = `<div id="center-container" style="position: fixed;top: 0;left: 0;width: 100%;height: 100%;display: flex;justify-content: center;align-items: center;background-color: rgba(0, 0, 0, 0.5);z-index: 9999;"><div style="width: 60%;background-color: rgba(0, 0, 0, 0.7);border: none;border-radius: 5px;padding: 20px 10px;font-size:1em;text-align: center;color: white;"><span id="countdown"></span> 秒後にもう一度チャレンジしてみてね！</div></div>`
	
	disableAnimation()
}

const secondsBetweenPlay = debug ? 10 : 2 * 60

let user = localStorage.getItem('user')
user = user ? JSON.parse(user) : {clist: [], last_ts: 0}
debug && console.log('user', user)

Array.prototype.shuffle = function () {
	// https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle

    let counter = this.length

    // While there are elements in the array
    while (counter > 0) {
        // Pick a random index
        let index = Math.floor(Math.random() * counter)

        // Decrease counter by 1
        counter--

        // And swap the last element with it
        let temp = this[counter]
        this[counter] = this[index]
        this[index] = temp
    }

    return this
}
addEventListener('load', async () => {
	shops = await weightedShopsPromise

	shops.forEach(s => s._weight = Math.pow(Math.random(), (1/s.weight)))
	shops.sort((a, b) => b._weight - a._weight)[0]

	for (let i = 0; shops.length > i; i++) {
		const shop = shops[i]
		shop.coupons = shop.coupons.filter(c => {
			const [, cuid] = c.url.match(/getkey=([a-z0-9]+)/i)
			if (cuid) {
				c.cuid = cuid
				return !user.clist.includes(c.id)
			} else {
				return false
			}
		})
		if (shop.coupons.length) {
			const shop = shops.splice(i, 1)[0]
			shops.unshift(shop)
			break
		}
	}

	if (currShopId && Math.random()<=0.5) {
		const i = shops.findIndex(s => s.shop_id===currShopId)
		const shop = shops.splice(i, 1)[0]
		shops.unshift(shop)
		rate = 100
		luck = 1
	}

	console.log({rate, luck})
	console.log(shops.map(s => `${s.shop_id}\t${s._weight}`).join('\n'))

	if (!shops[0].coupons || !shops[0].coupons.length) {
		return displayComeBackTomorrow()
	}

	images = shops.map(s => s.items).flat().map(i => i.images[0])
		.filter(url => !url.includes('/tj/r'))
		.filter(url => !url.includes('/tj/i'))
		.shuffle()


	const wi = images.findIndex(url => url.includes(shops[0].shop_id))
	const win_url = images.splice(wi, 1)[0]

	images = images.slice(0, SLOTS_PER_REEL)
	images.push(win_url)
	images = images.shuffle()
	winShopId = shops[0].shop_id
	winIndex = images.findIndex(url => url.includes(winShopId))
	debug && console.log({winIndex, winShopId})
	const r2 = document.querySelector('#ring2')
	createSlots(r2)
	r2.classList.add(`spin-${rand(0, 12)}`)

	const r3 = document.querySelector('#ring3')
	createSlots(r3)
	r3.classList.add(`spin-${rand(0, 12)}`)

	const r4 = document.querySelector('#ring4')
	createSlots(r4)
	r4.classList.add(`spin-${rand(0, 12)}`)

	if (+new Date - user.last_ts < secondsBetweenPlay * 1000) {
		return displayCanPlaySoon()
	}



	const btn = document.querySelector('#play')
	btn.addEventListener('click', () => {
		btn.disabled = true
		document.querySelector('#confetti').classList.remove('display-none')
		// lotteryPlayClick()
		// console.log('spin')
		spin()
	})
})
