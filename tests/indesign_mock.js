// Minimal fake InDesign DOM to exercise driver.js under Node:  node indesign_mock.js script.js
var fs = require('fs');
var written = {};
function Coll(items){ this.items = items; this.length = items.length; for (var i=0;i<items.length;i++) this[i]=items[i]; }
Coll.prototype.everyItem = function(){ var self=this; return { getElements: function(){ return self.items.slice(0); },
  cells: { everyItem: function(){ return { getElements: function(){ return []; } }; } } }; };
function Para(story, text, index, italicRanges){ this.story=story; this.contents=text; this.index=index;
  this.appliedParagraphStyle={name: /^Chapter/.test(text) ? 'Heading 1' : (/^Quote:/.test(text) ? 'Block Quote' : 'Body')};
  this.leftIndent = /^Indented:/.test(text) ? 36 : 0; this.firstLineIndent = 0;
  var self=this;
  this.textStyleRanges = new Coll((italicRanges||[[0,text.length,false]]).map(function(r){ return {fontStyle: r[2]?'Italic':'Regular', characters:{length:r[1]-r[0]}}; }));
  var ips=[]; for (var i=0;i<=text.length;i++) ips.push({index:i, para:self, parentTextFrames:[{parentPage:{name:String(story.page), documentOffset:story.page}}]});
  this.insertionPoints = ips;
  this.characters = { itemByRange: function(a,b){ return { applyConditions: function(c){ self.cond=(self.cond||[]).concat([[a,b,c[0].name]]); } }; } };
}
Para.prototype.toSpecifier = function(){ return 'p'+this.story.id+'_'+this.index; };
function Topic(name, sort){ this.name=name; this.sortOrder=sort; this.isValid=true; this.children={}; this.refs=[];
  var self=this;
  this.topics = { itemByName: function(n){ return self.children[n] || {isValid:false}; }, add: function(n,s){ var t=new Topic(n,s); self.children[n]=t; return t; },
                  everyItem: function(){ return {getElements: function(){ var o=[]; for (var k in self.children) o.push(self.children[k]); return o; }}; } };
  this.pageReferences = { add: function(ip, type){ var pr={ip:ip}; self.refs.push(pr); return pr; } };
  this.xrefs = [];
  this.crossReferences = { add: function(t, kind){ self.xrefs.push([t.name, kind]); return {}; } };
  this.remove = function(){};
}
var rootIndex = new Topic('ROOT','');
var paras = [];
var texts = JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
var stories = [];
texts.forEach(function(t, si){
  var st = {id: si, page: si+1};
  var idx = 0, ps = [];
  t.paras.forEach(function(pt){ var p = new Para(st, pt, idx, null); ps.push(p); idx += pt.length; });
  st.paragraphs = new Coll(ps);
  st.footnotes = new Coll((t.notes||[]).map(function(n){
    var fp = new Para({id: 'f'+si, page: si+1}, n.text, 0);
    return {storyOffset: {index: n.at}, texts: [{paragraphs: new Coll([fp])}]};
  }));
  st.tables = { everyItem: function(){ return { cells: { everyItem: function(){ return { getElements: function(){ return []; } }; } } }; } };
  st.textContainers = [{parentPage:{documentOffset: si}, geometricBounds:[0,0,0,0]}];
  stories.push(st);
});
var doc = { name: 'Test.indd', filePath: '/tmp', stories: new Coll(stories),
  indexes: { length: 0, add: function(){ this.length=1; this[0]=rootIndex; return rootIndex; } },
  characterStyles: { itemByName: function(){ return {isValid:false}; }, add: function(o){ return {name:o.name}; } },
  conditions: { itemByName: function(){ return {isValid:false}; }, add: function(o){ return {name:o.name}; } } };
global.app = { documents: {length:1}, activeDocument: doc, doScript: function(f){ f(); } };
global.ScriptLanguage = {JAVASCRIPT:1}; global.UndoModes = {ENTIRE_SCRIPT:1};
global.PageReferenceType = {CURRENT_PAGE:1}; global.ConditionIndicatorMethod={USE_HIGHLIGHT:1}; global.UIColors={YELLOW:1};
global.CrossReferenceType = {SEE: 'see', SEE_ALSO: 'see also'};
global.alert = function(m){ console.log('ALERT:', m); };
function F(path){ this.path=path; this.exists=false; this.eof=true; this.buf=''; }
F.prototype.open=function(){ return true; }; F.prototype.close=function(){ written[this.path]=this.buf; };
F.prototype.write=function(s){ this.buf+=s; }; F.prototype.writeln=function(s){ this.buf+=s+'\n'; }; F.prototype.readln=function(){ return ''; };
global.File = function(p){ return new F(p); }; global.Folder = {userData:'/tmp/ud', desktop:'/tmp'};
global.Window = function(){ return { add: function(type){ var o = {add: this.add, selection: null, value: false}; o.add=function(){ return o; }; return o; }, show: function(){ return 1; } }; };
// dropdown selection objects
var _origWin = global.Window;
global.Window = function(){ var w = { alignChildren:'', add: function(type, b, items){ var c = { alignment:'', value:true,
   add: function(t2, b2, items2){ if (t2==='dropdownlist') return { selection:{index:0}, set selection2(v){} }; if (t2==='checkbox') return {value:true}; return { add: function(){ return {}; }, alignment:'' }; } };
   if (type==='dropdownlist') { return { _s:{index:0}, get selection(){ return this._s; }, set selection(v){ this._s={index: (typeof v==='number'?v:v.index)}; } }; }
   if (type==='checkbox') return {value:true};
   if (type==='panel') { return { add: function(t2){ if (t2==='dropdownlist') return { _s:{index:0}, get selection(){ return this._s; }, set selection(v){ this._s={index:(typeof v==='number'?v:v.index)}; } }; if (t2==='checkbox') return {value:true}; return {}; } }; }
   return c; }, show: function(){ return 1; } }; return w; };
// ExtendScript quirk: splice() returns undefined when it removes nothing
var _splice = Array.prototype.splice;
Array.prototype.splice = function(){ var r = _splice.apply(this, arguments); return r.length ? r : undefined; };
eval(fs.readFileSync(process.argv[2],'utf8').replace('#target indesign',''));
function dump(t, d){ var o=''; for (var k in t.children){ var c=t.children[k]; o += Array(d+1).join('  ') + c.name + ' [' + c.sortOrder + ']' + (c.refs.length? ' x'+c.refs.length : '') + (c.xrefs.length ? ' ' + JSON.stringify(c.xrefs) : '') + '\n' + dump(c, d+1); } return o; }
console.log(dump(rootIndex,0));
for (var k in written) console.log('FILE', k, written[k].length, 'chars');
var html = written['/tmp/Test - Index Proof List.html'] || '';
console.log(html.split('\n').slice(4, 9).join('\n').slice(0, 1200));
