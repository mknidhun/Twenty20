# Auth Testing Playbook

## MongoDB Verification
```
mongosh
use twenty20_wariyad
db.users.find({role: "super_admin"}).pretty()
db.users.findOne({role: "super_admin"}, {password_hash: 1})
```
Verify: bcrypt hash starts with `$2b$`

## API Testing
```bash
# Login
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@twenty20wariyad.com","password":"Admin@20W20"}'

# Check session
curl -b cookies.txt http://localhost:8001/api/auth/me

# View cookies
cat cookies.txt
```

## Admin Credentials
- Email: admin@twenty20wariyad.com
- Password: Admin@20W20
- Role: super_admin
