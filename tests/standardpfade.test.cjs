const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../mail_merge/mail_merge/doctype/serienbrief_textbaustein/serienbrief_textbaustein.js'), 'utf8');
function form(variables, mapping) {
 const target = {doctype:'Standardpfad',name:'row',startobjekt:'Mietvertrag',pfad_zuordnung:JSON.stringify(mapping)};
 return {doc:{name:'Block',variables,standardpfade:[target]},refresh_field(){},add_child(){throw Error('unexpected new row');}};
}
function harness(frm, pendingMeta = false) {
 const inputs = []; const messages = []; const metaCallbacks = [];
 class Element {
  constructor(kind=''){this.kind=kind;this[0]=this;this.events={};}
  empty(){return this;} append(){return this;} text(){return this;} html(){return this;} find(){return new Element();}
  val(v){if(arguments.length){this.value=v;return this;}return this.value;}
  on(e,fn){this.events[e]=fn;return this;} prop(){return this;}
 }
 class Dialog {
  constructor(options){this.options=options;this.fields_dict={startobjekt:{$input:new Element()}};this.start=options.fields[0].default;api.dialog=this;}
  get_field(){return {wrapper:new Element()};}get_value(){return this.start;}show(){}hide(){}
 }
 const api={};
 const context=vm.createContext({__:(s)=>s,window:{},$:(value)=>{
  if(value instanceof Element)return value;
  const el=new Element(String(value));if(el.kind.includes('<input'))inputs.push(el);return el;
 },frappe:{ui:{form:{on(){}},Dialog},get_meta:()=>({fields:[]}),msgprint:(v)=>messages.push(v),utils:{escape_html:(s)=>s},model:{with_doctype:(dt,cb)=>pendingMeta?metaCallbacks.push(cb):cb(),set_value:(dt,name,key,value)=>{frm.doc.standardpfade.find(r=>r.name===name)[key]=value;}}}});
 vm.runInContext(source+'\nglobalThis.getInputs = hv_get_input_requirements; globalThis.openPaths = hv_open_default_path_dialog;',context);
 api.open=()=>context.openPaths(frm);api.requirements=()=>context.getInputs(frm);api.inputs=inputs;api.messages=messages;api.metaCallbacks=metaCallbacks;
 return api;
}
const variables=[{name:'old-address-row',variable:'address',variable_type:'Doctype',reference_doctype:'Address'},{name:'old-date-row',variable:'datum',variable_type:'Text'},{variable:'druck_schwarz_weiss',variable_type:'Bool'}];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('all input types use renderer variable names, not child IDs',()=>{
 const api=harness(form([...variables,{variable:'betrag',variable_type:'Zahl'},{variable:'termin',variable_type:'Datum'},{variable:'namen',variable_type:'Doctype Liste',reference_doctype:'Contact'}],{}));
 assert.deepEqual(Array.from(api.requirements(),r=>r.req_key),['address','datum','druck_schwarz_weiss','betrag','termin','namen']);
});
test('actual dialog save and reopen retain scalar and additional paths',async()=>{
 const mapping={address:'objekt.kunde.briefanschrift',datum:'datum',druck_schwarz_weiss:'druck_schwarz_weiss',extra:'objekt.extra'};
 const frm=form(variables,mapping),api=harness(frm);api.open();await tick();
 assert.equal(api.inputs.length,3);assert.equal(api.inputs[1].val(),'datum');assert.equal(api.inputs[2].val(),'druck_schwarz_weiss');
 await api.dialog.options.primary_action({startobjekt:'Mietvertrag'});
 assert.deepEqual(JSON.parse(frm.doc.standardpfade[0].pfad_zuordnung),mapping);
 api.open();await tick();await api.dialog.options.primary_action({startobjekt:'Mietvertrag'});
 assert.deepEqual(JSON.parse(frm.doc.standardpfade[0].pfad_zuordnung),mapping);
});
test('legacy keys become canonical and explicitly cleared fields stay cleared',async()=>{
 const frm=form(variables,{'old-address-row':'objekt.alt',Address:'objekt.fallback',datum:'datum',druck_schwarz_weiss:'druck_schwarz_weiss',extra:'extra'}),api=harness(frm);api.open();await tick();
 assert.equal(api.inputs[0].val(),'objekt.alt');api.inputs[1].val('');
 await api.dialog.options.primary_action({startobjekt:'Mietvertrag'});
 assert.deepEqual(JSON.parse(frm.doc.standardpfade[0].pfad_zuordnung),{address:'objekt.alt',druck_schwarz_weiss:'druck_schwarz_weiss',extra:'extra'});
});
test('scalar-only block can configure standard paths',async()=>{
 const frm=form(variables.slice(1),{datum:'datum',druck_schwarz_weiss:'druck_schwarz_weiss'}),api=harness(frm);api.open();await tick();
 assert.equal(api.inputs.length,2);await api.dialog.options.primary_action({startobjekt:'Mietvertrag'});
 assert.deepEqual(JSON.parse(frm.doc.standardpfade[0].pfad_zuordnung),{datum:'datum',druck_schwarz_weiss:'druck_schwarz_weiss'});
});
test('save during metadata loading cannot erase paths',async()=>{
 const frm=form(variables,{datum:'datum'}),api=harness(frm,true);api.open();
 await api.dialog.options.primary_action({startobjekt:'Mietvertrag'});
 assert.equal(api.messages.length,1);assert.deepEqual(JSON.parse(frm.doc.standardpfade[0].pfad_zuordnung),{datum:'datum'});
 api.metaCallbacks[0]();await tick();
});
