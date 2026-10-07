//===============================================================
// debounce関数
//===============================================================
function debounce(func, wait) {
    var timeout;
    return function() {
        var context = this, args = arguments;
        var later = function() {
            timeout = null;
            func.apply(context, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}


//===============================================================
// メニュー関連
//===============================================================

// 変数でセレクタを管理
var $menubar = $('#menubar');
var $menubarHdr = $('#menubar_hdr');
var $headerNav = $('header nav');

// menu
$(window).on("load resize", debounce(function() {
    if(window.innerWidth < 9999) {	// ここがブレイクポイント指定箇所です
        // 小さな端末用の処理
        $('body').addClass('small-screen').removeClass('large-screen');
        $menubar.addClass('display-none').removeClass('display-block');
        $menubarHdr.removeClass('display-none ham').addClass('display-block');
    } else {
        // 大きな端末用の処理
        $('body').addClass('large-screen').removeClass('small-screen');
        $menubar.addClass('display-block').removeClass('display-none');
        $menubarHdr.removeClass('display-block').addClass('display-none');

        // ドロップダウンメニューが開いていれば、それを閉じる
        $('.ddmenu_parent > ul').hide();
    }
}, 10));

$(function() {

    // ハンバーガーメニューをクリックした際の処理
    $menubarHdr.click(function() {
        $(this).toggleClass('ham');
        if ($(this).hasClass('ham')) {
            $menubar.addClass('display-block');
        } else {
            $menubar.removeClass('display-block');
        }
    });

    // アンカーリンクの場合にメニューを閉じる処理
    $menubar.find('a[href*="#"]').click(function() {
        $menubar.removeClass('display-block');
        $menubarHdr.removeClass('ham');
    });

    // ドロップダウンの親liタグ（空のリンクを持つaタグのデフォルト動作を防止）
	$menubar.find('a[href=""]').click(function() {
		return false;
	});
	$headerNav.find('a[href=""]').click(function() {
		return false;
	});

	// ドロップダウンメニューの処理
    $menubar.find('li:has(ul)').addClass('ddmenu_parent');
    $('.ddmenu_parent > a').addClass('ddmenu');
    $headerNav.find('li:has(ul)').addClass('ddmenu_parent');
    $('.ddmenu_parent > a').addClass('ddmenu');

// タッチ開始位置を格納する変数
var touchStartY = 0;

// タッチデバイス用
$('.ddmenu').on('touchstart', function(e) {
    // タッチ開始位置を記録
    touchStartY = e.originalEvent.touches[0].clientY;
}).on('touchend', function(e) {
    // タッチ終了時の位置を取得
    var touchEndY = e.originalEvent.changedTouches[0].clientY;
    
    // タッチ開始位置とタッチ終了位置の差分を計算
    var touchDifference = touchStartY - touchEndY;
    
    // スクロール動作でない（差分が小さい）場合にのみドロップダウンを制御
    if (Math.abs(touchDifference) < 10) { // 10px以下の移動ならタップとみなす
        var $nextUl = $(this).next('ul');
        if ($nextUl.is(':visible')) {
            $nextUl.stop().hide();
        } else {
            $nextUl.stop().show();
        }
        $('.ddmenu').not(this).next('ul').hide();
        return false; // ドロップダウンのリンクがフォローされるのを防ぐ
    }
});

    //PC用
    $('.ddmenu_parent').hover(function() {
        $(this).children('ul').stop().show();
    }, function() {
        $(this).children('ul').stop().hide();
    });

    // ドロップダウンをページ内リンクで使った場合に、ドロップダウンを閉じる
    $('.ddmenu_parent ul a').click(function() {
        $('.ddmenu_parent > ul').hide();
    });

});


//===============================================================
// 小さなメニューが開いている際のみ、body要素のスクロールを禁止。
//===============================================================
$(document).ready(function() {
  function toggleBodyScroll() {
    // 条件をチェック
    if ($('#menubar_hdr').hasClass('ham') && !$('#menubar_hdr').hasClass('display-none')) {
      // #menubar_hdr が 'ham' クラスを持ち、かつ 'display-none' クラスを持たない場合、スクロールを禁止
      $('body').css({
        overflow: 'hidden',
        height: '100%'
      });
    } else {
      // その他の場合、スクロールを再び可能に
      $('body').css({
        overflow: '',
        height: ''
      });
    }
  }

  // 初期ロード時にチェックを実行
  toggleBodyScroll();

  // クラスが動的に変更されることを想定して、MutationObserverを使用
  const observer = new MutationObserver(toggleBodyScroll);
  observer.observe(document.getElementById('menubar_hdr'), { attributes: true, attributeFilter: ['class'] });
});


//===============================================================
// スムーススクロール（※バージョン2024-1）※通常タイプ
//===============================================================
$(function() {
    // ページ上部へ戻るボタンのセレクター
    var topButton = $('.pagetop');
    // ページトップボタン表示用のクラス名
    var scrollShow = 'pagetop-show';

    // スムーススクロールを実行する関数
    // targetにはスクロール先の要素のセレクターまたは'#'（ページトップ）を指定
    function smoothScroll(target) {
        // スクロール先の位置を計算（ページトップの場合は0、それ以外は要素の位置）
        var scrollTo = target === '#' ? 0 : $(target).offset().top;
        // アニメーションでスムーススクロールを実行
        $('html, body').animate({scrollTop: scrollTo}, 500);
    }

    // ページ内リンクとページトップへ戻るボタンにクリックイベントを設定
    $('a[href^="#"], .pagetop').click(function(e) {
        e.preventDefault(); // デフォルトのアンカー動作をキャンセル
        var id = $(this).attr('href') || '#'; // クリックされた要素のhref属性を取得、なければ'#'
        smoothScroll(id); // スムーススクロールを実行
    });

    // スクロールに応じてページトップボタンの表示/非表示を切り替え
    $(topButton).hide(); // 初期状態ではボタンを隠す
    $(window).scroll(function() {
        if($(this).scrollTop() >= 300) { // スクロール位置が300pxを超えたら
            $(topButton).fadeIn().addClass(scrollShow); // ボタンを表示
        } else {
            $(topButton).fadeOut().removeClass(scrollShow); // それ以外では非表示
        }
    });

    // ページロード時にURLのハッシュが存在する場合の処理
    if(window.location.hash) {
        // ページの最上部に即時スクロールする
        $('html, body').scrollTop(0);
        // 少し遅延させてからスムーススクロールを実行
        setTimeout(function() {
            smoothScroll(window.location.hash);
        }, 10);
    }
});


//===============================================================
// 汎用開閉処理
//===============================================================
$(function() {
	$('.openclose').next().hide();
	$('.openclose').click(function() {
		$(this).next().slideToggle();
		$('.openclose').not(this).next().slideUp();
	});
});


//===============================================================
// テキストのフェードイン効果
//===============================================================
$(function() {
    $('.fade-in-text').on('inview', function(event, isInView) {
        // この要素が既にアニメーションされたかどうかを確認
        if (isInView && !$(this).data('animated')) {
            // アニメーションがまだ実行されていない場合
            let innerHTML = '';
            const text = $(this).text();
            $(this).text('');

            for (let i = 0; i < text.length; i++) {
                innerHTML += `<span class="char" style="animation-delay: ${i * 0.1}s;">${text[i]}</span>`;
            }

            $(this).html(innerHTML).css('visibility', 'visible');
            // アニメーションが実行されたことをマーク
            $(this).data('animated', true);
        }
    });
});


//===============================================================
// 背景切り替え
//===============================================================
$(document).ready(function () {
  function checkVisibility() {
    const viewportHeight = $(window).height();
    const scrollTop = $(window).scrollTop();

    $(".section").each(function () {
      const sectionTop = $(this).offset().top;
      const sectionHeight = $(this).outerHeight();

      if (
        sectionTop < scrollTop + viewportHeight * 0.6 &&
        sectionTop + sectionHeight > scrollTop + viewportHeight * 0.4
      ) {
        $(this).addClass("active").removeClass("inactive");

        // セクションのIDを取得
        var sectionId = $(this).attr("id");

        // すべてのメニュー項目からactiveクラスを削除
        $("#header-menu li").removeClass("active");

        // 対応するメニュー項目にactiveクラスを追加
        $('#header-menu li a[href="#' + sectionId + '"]')
          .parent()
          .addClass("active");
      } else {
        $(this).addClass("inactive").removeClass("active");
      }
    });
  }

  $(window).on("scroll", checkVisibility);
  checkVisibility();
});


//===============================================================
// 横スライドインタイプのスライドショー
//===============================================================
$(function() {
    $('.slide5').each(function() {
        var $this = $(this);
        var slides = $this.find('.slide');
        var slideCount = slides.length;
        var currentIndex = 0;
        var isAnimating = false;

        // インジケータを表示する要素を取得
        var indicators = $this.find('.slide-indicators');

        // スライドの数に応じたインジケータを生成
        for (var i = 0; i < slideCount; i++) {
            indicators.append('<span class="indicator" data-index="' + i + '"></span>');
        }

        // インジケータの初期状態を設定
        var indicatorElements = indicators.find('.indicator');
        indicatorElements.eq(currentIndex).addClass('active');

        // 初期状態で全てのスライドに .hidden クラスを追加
        slides.addClass('hidden');

        // 最初のスライドに .active と .initial クラスを追加し、.hidden クラスを削除
        slides.eq(currentIndex).addClass('active initial').removeClass('hidden');

        // 遅延後に .initial クラスを削除
        setTimeout(function() {
            slides.eq(currentIndex).removeClass('initial');
        }, 50);

        // インジケータをクリックしたときの動作を設定
        indicatorElements.on('click', function() {
            var clickedIndex = $(this).data('index');

            // アニメーション中は操作を受け付けない
            if (isAnimating) return;

            // 現在のスライドと同じ場合は何もしない
            if (clickedIndex === currentIndex) return;

            // スライドの切り替え
            changeSlide(clickedIndex);
        });

        // 自動スライドのタイマー
        setInterval(function() {
            var nextIndex = (currentIndex + 1) % slideCount;
            changeSlide(nextIndex);
        }, 4000); // 4秒ごとにスライドを切り替える

        function changeSlide(nextIndex) {
            isAnimating = true;

            // 現在のスライドを左に移動
            slides.eq(currentIndex).removeClass('active').addClass('left');

            // 次のスライドを表示
            slides.eq(nextIndex).addClass('active').removeClass('hidden');

            // インジケータの更新
            indicatorElements.eq(currentIndex).removeClass('active');
            indicatorElements.eq(nextIndex).addClass('active');

            // アニメーション終了後の処理
            setTimeout(function() {
                // 左に移動したスライドに .hidden クラスを追加
                slides.eq(currentIndex).removeClass('left').addClass('hidden');

                currentIndex = nextIndex;
                isAnimating = false;
            }, 700); // cssの「.slide5 .slide」の行の時間と合わせる
        }
    });
});


//===============================================================
// サムネイルスライドショー
//===============================================================
$(document).ready(function() {
    $('.slide-thumbnail1 .img').each(function() {
        var $imgParts = $(this);
        var $divs = $imgParts.children('div');
        var divCount = $divs.length;

        // 各 div の幅を計算
        var divWidth = 100 / (divCount * 2);

        // 基準値と速度係数を定義
        var baseAnimationTime = 10; // 「10がアニメーションの速度。小さいと早く、大きいとゆっくりになります。
        var baseSlideWidth = 200;
        var speedFactor = divCount / 2;	// 画面内に表示させる枚数。２枚。

        // アニメーション時間とスライド幅を計算
        var animationTime = (baseAnimationTime * speedFactor) + 's';
        var slideWidth = (baseSlideWidth * speedFactor) + '%';

        // 各 div に幅を設定
        $divs.css({
            'flex': '0 0 ' + divWidth + '%',
            'width': divWidth + '%'
        });

        // .img に animation と width を設定
        $imgParts.css({
            'animation-duration': animationTime,
            'width': slideWidth
        });

        // 子要素を複製して追加
        $divs.clone().appendTo($imgParts);

        // アニメーションの一時停止と再開
        $imgParts.on('mouseenter', function() {
            $(this).css('animation-play-state', 'paused');
        });
        $imgParts.on('mouseleave', function() {
            $(this).css('animation-play-state', 'running');
        });
    });
});

//===============================================================
// ゆめはん専用：全スライド共通「水着と同じ速度」＋最高の操作感（完成版）
//===============================================================
$(function () {
    $('.slide-thumbnail1').each(function () {
        const $container = $(this);
        const $track = $container.find('.img');
        const isRTL = $track.hasClass('rtl');

        // 水着に完全に合わせた物理速度（画像枚数に関係なく常に同じ速度！）
        const PIXELS_PER_SECOND = 2;          // ← これが水着と同じ速度です（70〜80で微調整可）

        // ★ここを調整しました★
        const SWIPE_MULTIPLIER   = 0.001;                    // スワイプ中の追従感度（変更なしで自然）
        const INERTIA_MULTIPLIER  = 0.008 * (1/10);           // ← 慣性を1/10に抑える
        const FRICTION           = 0.95 * (1/10);             // 慣性減衰率（変更なしでOK）
        const RESUME_DELAY       = 2000;                     // ← タップ停止後の再開時間

        let isDragging = false;
        let isPaused = false;
        let startX = 0;
        let currentX = 0;
        let translateX = isRTL ? 0 : -50;
        let velocity = 0;
        let raf = null;
        let slowRaf = null;
        let lastTime = performance.now();
        let resumeTimer = null;

        const containerWidth = $container.width();
        const percentPerPixel = 100 / containerWidth;

        const seamlessLoop = () => {
            if (isRTL) {
                while (translateX >= 0) translateX -= 100;
                while (translateX < -100) translateX += 100;
            } else {
                while (translateX <= -100) translateX += 100;
                while (translateX > -50) translateX -= 50;
            }
        };

        const slowScroll = (now) => {
            if (isPaused || isDragging) return;
            if (!lastTime) lastTime = now;
            const delta = (now - lastTime) / 1000;
            lastTime = now;

            const pixelMove = PIXELS_PER_SECOND * delta;
            const percentMove = pixelMove * percentPerPixel;
            translateX += (isRTL ? 1 : -1) * percentMove;

            seamlessLoop();
            $track.css('transform', `translateX(${translateX}%)`);
            slowRaf = requestAnimationFrame(slowScroll);
        };

        const inertia = () => {
            translateX += velocity;
            velocity *= 0.95;
            seamlessLoop();
            $track.css('transform', `translateX(${translateX}%)`);
            if (Math.abs(velocity) > 0.3) {
                raf = requestAnimationFrame(inertia);
            } else {
                velocity = 0;
                if (!isPaused) slowRaf = requestAnimationFrame(slowScroll);
            }
        };

        // タッチ／マウス操作
        $container.on('touchstart mousedown', function (e) {
            if (isPaused) return;
            isDragging = true;
            cancelAnimationFrame(slowRaf);
            cancelAnimationFrame(raf);
            clearTimeout(resumeTimer);

            const clientX = e.originalEvent?.touches?.[0].clientX || e.clientX;
            startX = currentX = clientX;
            velocity = 0;
            if (e.type === 'mousedown') e.preventDefault();
        });

        $container.on('touchmove mousemove', function (e) {
            if (!isDragging || isPaused) return;
            const clientX = e.originalEvent?.touches?.[0].clientX || e.clientX;
            const deltaX = clientX - currentX;
            currentX = clientX;

            const deltaPercent = deltaX * percentPerPixel;
            translateX += deltaPercent * SWIPE_MULTIPLIER * 100;
            velocity = deltaPercent * INERTIA_MULTIPLIER * 100;

            seamlessLoop();
            $track.css('transform', `translateX(${translateX}%)`);
            if (Math.abs(deltaX) > 5) e.preventDefault();
        });

        $(document).on('touchend mouseup mouseleave', function () {
            if (!isDragging) return;
            isDragging = false;
            if (Math.abs(velocity) > 0.5) {
                raf = requestAnimationFrame(inertia);
            } else if (!isPaused) {
                lastTime = performance.now();
                slowRaf = requestAnimationFrame(slowScroll);
            }
        });

        // タップで停止＆リンク
        $container.on('click', function (e) {
            const moved = Math.abs(currentX - startX);
            if (moved > 15) { e.preventDefault(); return; }
            e.preventDefault();
            if (isPaused) {
                isPaused = false;
                clearTimeout(resumeTimer);
                const link = e.target.closest('a');
                if (link) window.location.href = link.href;
            } else {
                isPaused = true;
                cancelAnimationFrame(slowRaf);
                cancelAnimationFrame(raf);
                clearTimeout(resumeTimer);
                resumeTimer = setTimeout(() => {
                    isPaused = false;
                    lastTime = performance.now();
                    slowRaf = requestAnimationFrame(slowScroll);
                }, RESUME_DELAY);
            }
        });

        // スタート
        lastTime = performance.now();
        slowRaf = requestAnimationFrame(slowScroll);
    });
});

//===============================================================
// ゆめはん専用 営業日カレンダー（最終完全版：同期完璧・クリック・矢印のみ）
//===============================================================
$(function () {
    const $cal   = $('.yumekan-calendar-mini');
    const $title = $cal.find('.month-title');
    const $grid  = $cal.find('#daysGrid');
    const $status= $('#todayStatus');

    let currentYear  = new Date().getFullYear();
    let currentMonth = new Date().getMonth(); // 0〜11

    // ─────── 追加休業日（ここに自由に追加）───────
    const extraHolidays = [
        '2025-12-29','2025-12-30','2025-12-31',
        '2026-01-01','2026-01-02','2026-01-03'
    ];

    // ─────── 日本の祝日（2025年11/24振替休日も含む）───────
    const holidays = {
        '01-01':'元日','01-13':'成人の日','02-11':'建国記念の日','02-23':'天皇誕生日',
        '03-20':'春分の日','04-29':'昭和の日','05-03':'憲法記念日','05-04':'みどりの日',
        '05-05':'こどもの日','05-06':'振替休日','07-21':'海の日','08-11':'山の日',
        '09-15':'敬老の日','09-23':'秋分の日','10-13':'スポーツの日','11-03':'文化の日',
        '11-23':'勤労感謝の日','11-24':'振替休日'
    };

    function render() {
        $grid.empty();

        const today      = new Date();
        const todayYear  = today.getFullYear();
        const todayMonth = today.getMonth();
        const todayDate  = today.getDate();
        const todayStr   = `${todayYear}-${String(todayMonth+1).padStart(2,'0')}-${String(todayDate).padStart(2,'0')}`;

        // ヘッダー
        $title.text(`${currentYear}年 ${currentMonth + 1}月`);

        // 本日の営業状況（リアルタイムで常に正しい日付）
        const isHoliday = today.getDay() === 0 || today.getDay() === 6 ||
            holidays[`${String(todayMonth+1).padStart(2,'0')}-${String(todayDate).padStart(2,'0')}`] ||
            extraHolidays.includes(todayStr);

        $status.text(isHoliday 
            ? `本日はお休みです (${todayMonth+1}/${todayDate})`
            : `本日は営業中です (${todayMonth+1}/${todayDate})`)
               .css('color', isHoliday ? '#e91e63' : '#2e7d32');

        // カレンダー描画
        const firstDate   = new Date(currentYear, currentMonth, 1);
        const firstDay    = firstDate.getDay();                   // 0=日曜
        const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

        // 前月
        const prevMonthDays = new Date(currentYear, currentMonth, 0).getDate();
        for (let i = firstDay - 1; i >= 0; i--) {
            $('<div>').addClass('day other-month').text(prevMonthDays - i).appendTo($grid);
        }

        // 当月
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${currentYear}-${String(currentMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const thisDate = new Date(currentYear, currentMonth, d);
            const isSun = thisDate.getDay() === 0;
            const isSat = thisDate.getDay() === 6;
            const key = `${String(currentMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const isHolidayDay = holidays[key] || extraHolidays.includes(dateStr);
            const isToday = dateStr === todayStr;

            const $day = $('<div>').addClass('day').text(d);
            if (isToday) $day.addClass('today');
            if (isSun || isSat || isHolidayDay) $day.addClass('holiday');
            $grid.append($day);
        }

        // 次月（埋め草）
        const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7;
        const remaining = totalCells - firstDay - daysInMonth;
        for (let i = 1; i <= remaining; i++) {
            $('<div>').addClass('day other-month').text(i).appendTo($grid);
        }
    }

    // ─────── 矢印ボタンのみ（スワイプ・日付クリック完全排除）───────
    $cal.find('.prev').on('click', function () {
        if (currentMonth === 0) { currentMonth = 11; currentYear--; }
        else currentMonth--;
        render();
    });

    $cal.find('.next').on('click', function () {
        if (currentMonth === 11) { currentMonth = 0; currentYear++; }
        else currentMonth++;
        render();
    });

    // 初回描画（ページ読み込み時に今日が正しく表示されます）
    render();
});