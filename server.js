import 'dotenv/config';
import express from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { MongoClient, BSON } from 'mongodb';
import { timingSafeEqual, createHash } from 'node:crypto';
import { once } from 'node:events';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const app=express(); const root=path.dirname(fileURLToPath(import.meta.url));
app.disable('x-powered-by'); app.use(helmet()); app.use(rateLimit({windowMs:60000,limit:180}));
app.use((req,res,next)=>{res.set('Cache-Control','no-store'); const u=process.env.ADMIN_USER,p=process.env.ADMIN_PASSWORD; if(!u||!p||p.length<16)return res.status(503).send('Configure ADMIN_USER e ADMIN_PASSWORD (mínimo 16 caracteres).'); const expected=Buffer.from(u+':'+p); let actual=Buffer.alloc(0); if(req.headers.authorization?.startsWith('Basic ')) actual=Buffer.from(req.headers.authorization.slice(6),'base64'); const hash=x=>createHash('sha256').update(x).digest(); if(!timingSafeEqual(hash(expected),hash(actual))){res.set('WWW-Authenticate','Basic realm="Maximum Recovery", charset="UTF-8"');return res.status(401).send('Autenticação necessária.');}next();});
let connection; async function client(){if(!process.env.MONGODB_URI)throw Error('Configure MONGODB_URI'); if(!connection){const c=new MongoClient(process.env.MONGODB_URI,{serverSelectionTimeoutMS:10000,maxPoolSize:5});connection=c.connect().catch(async e=>{connection=undefined;await c.close();throw e;});}return connection;}
async function databases(){const c=await client(); if(process.env.MONGODB_DB)return [process.env.MONGODB_DB]; const r=await c.db('admin').admin().listDatabases({nameOnly:true,authorizedDatabases:true});return r.databases.map(x=>x.name).filter(x=>!['admin','local','config'].includes(x));}
async function db(name){if(typeof name!=='string'||!(await databases()).includes(name))throw Object.assign(Error('Banco não autorizado'),{status:400});return (await client()).db(name);}
async function coll(req){const d=await db(req.query.db);const n=req.query.collection;if(typeof n!=='string'||!(await d.listCollections({name:n},{nameOnly:true}).toArray()).some(x=>x.name===n&&!n.startsWith('system.')))throw Object.assign(Error('Coleção não encontrada'),{status:400});return d.collection(n);}
const redact=new Set(['password','passwordhash','senha','hashsenha','token','accesstoken','refreshtoken','secret','sessionsecret','apikey','salt','credential','credentials']);
function clean(x){if(Array.isArray(x))return x.map(clean);if(x&&typeof x==='object'){return Object.fromEntries(Object.entries(x).map(([k,v])=>[k,redact.has(k.toLowerCase().replace(/[^a-z]/g,''))?'[OCULTO]':clean(v)]));}return x;}
const safe=x=>clean(BSON.EJSON.serialize(x,{relaxed:false}));
app.get('/api/databases',async(req,res)=>res.json(await databases()));
app.get('/api/collections',async(req,res)=>{const d=await db(req.query.db);const rows=await d.listCollections({}, {nameOnly:true}).toArray();res.json(rows.filter(x=>!x.name.startsWith('system.')).map(x=>x.name).sort());});
function filter(req){const field=req.query.field,q=req.query.q;if(!q)return {};if(typeof field!=='string'||!/^[a-zA-Z0-9_.-]{1,120}$/.test(field)||field.split('.').some(x=>!x||x.startsWith('$'))||typeof q!=='string'||q.length>200)throw Object.assign(Error('Filtro inválido'),{status:400});return {[field]:{$regex:q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),$options:'i'}};}
app.get('/api/records',async(req,res)=>{const c=await coll(req),f=filter(req),page=Math.min(100000,Math.max(1,parseInt(req.query.page)||1));const [total,rows]=await Promise.all([c.countDocuments(f,{maxTimeMS:15000}),c.find(f).sort({_id:1}).skip((page-1)*50).limit(50).maxTimeMS(15000).toArray()]);res.json({total,page,rows:rows.map(safe)});});
app.get('/api/export',async(req,res)=>{const c=await coll(req),f=filter(req);const csv=req.query.format==='csv';const cursor=c.find(f).sort({_id:1}).maxTimeMS(120000);res.attachment(csv?'registros.csv':'registros.json');res.type(csv?'text/csv':'application/json');const quote=v=>'"'+String(v??'').replace(/^[=+\-@\t\r]/,"'$&").replaceAll('"','""')+'"';const write=async x=>{if(!res.write(x))await once(res,'drain');};let first=true;try{await write(csv?'\ufeff_id,documento_json\r\n':'[\n');for await(const row of cursor){if(res.destroyed)break;const doc=safe(row);await write(csv?quote(JSON.stringify(doc._id))+','+quote(JSON.stringify(doc))+'\r\n':(first?'':',\n')+JSON.stringify(doc));first=false;}if(!res.destroyed)res.end(csv?'':'\n]');}finally{await cursor.close();}});
app.use(express.static(path.join(root,'public')));app.use((err,req,res,next)=>{console.error(err.name,err.code??'');if(res.headersSent)return res.destroy();res.status(err.status||500).json({error:err.status?err.message:'Falha na consulta. Confira URI, permissões de leitura, nome do banco e lista de IPs do MongoDB.'});});
if(!process.env.VERCEL)app.listen(Number(process.env.PORT)||3000,process.env.HOST||'127.0.0.1',()=>console.log('Maximum Recovery: http://localhost:'+(process.env.PORT||3000)));export default app;
