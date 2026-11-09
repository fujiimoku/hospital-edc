const {test}=require('node:test'),assert=require('node:assert/strict'),{chromium}=require('playwright'),fs=require('fs');
test('radio clicks and Enter keep outer frame stationary',async()=>{
 const b=await chromium.launch({headless:true,executablePath:process.env.EDC_TEST_BROWSER});try{
 const p=await b.newPage({viewport:{width:1000,height:700}});
 await p.setContent(`<style>html,body{margin:0;height:100%;overflow:hidden}body{display:flex}aside{width:150px}main{display:flex;flex:1;flex-direction:column;overflow:hidden}header{height:60px;flex-shrink:0}#content{flex:1;overflow-y:auto}label{display:block;height:170px;border:1px solid} .hidden{display:none}</style><aside>sidebar</aside><main><header>header</header><div id="content"><div id="entry-form-area"><div class="tab-panel">${Array.from({length:12},(_,i)=>`<label><input type="radio" class="hidden" name="dtsq-q${i}" value="5">question ${i}</label>`).join('')}</div></div></div></main>`);
 await p.addStyleTag({path:'hospital-edc-frontend/css/main.css'});await p.addScriptTag({path:'hospital-edc-frontend/js/entry-keyboard.js'});await p.evaluate(()=>EntryKeyboard.setup(document.getElementById('entry-form-area')));
 for(let i=0;i<10;i++){await p.locator('label').nth(i).click();await p.keyboard.press('Enter');}
 const state=await p.evaluate(()=>({body:document.body.scrollTop,html:document.documentElement.scrollTop,main:document.querySelector('main').scrollTop,header:document.querySelector('header').getBoundingClientRect().top}));console.log(state);assert.deepEqual(state,{body:0,html:0,main:0,header:0});
 }finally{await b.close();}
});
