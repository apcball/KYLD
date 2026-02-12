-- Quick Diagnostic Query for PO Portal Signature Issue
-- Run this to check which users can use auto-approval

-- Query 1: Overall status of all users
SELECT 
    u.id as user_id,
    u.login,
    COALESCE(p.name, 'N/A') as user_name,
    CASE 
        WHEN u.employee_id IS NULL THEN '❌ No Employee Linked'
        WHEN e.signature_image IS NULL THEN '❌ No Signature'
        ELSE '✅ Ready for Auto-Approval'
    END as status,
    e.id as employee_id,
    COALESCE(e.name, 'N/A') as employee_name
FROM res_users u
LEFT JOIN res_partner p ON u.partner_id = p.id
LEFT JOIN hr_employee e ON u.employee_id = e.id
WHERE u.active = true 
  AND u.id NOT IN (1, 2)  -- Exclude system users
ORDER BY status DESC, u.login;

-- Query 2: Find users who need attention
SELECT 
    'Missing Employee Link' as issue_type,
    u.login,
    p.name as user_name
FROM res_users u
INNER JOIN res_partner p ON u.partner_id = p.id
WHERE u.active = true 
  AND u.employee_id IS NULL
  AND u.id NOT IN (1, 2)

UNION ALL

SELECT 
    'Missing Signature' as issue_type,
    u.login,
    e.name as employee_name
FROM res_users u
INNER JOIN hr_employee e ON u.employee_id = e.id
WHERE u.active = true
  AND e.signature_image IS NULL
  AND u.id NOT IN (1, 2)
ORDER BY issue_type, user_name;

-- Query 3: Count summary
SELECT 
    COUNT(*) FILTER (WHERE u.employee_id IS NULL) as users_without_employee,
    COUNT(*) FILTER (WHERE u.employee_id IS NOT NULL AND e.signature_image IS NULL) as employees_without_signature,
    COUNT(*) FILTER (WHERE u.employee_id IS NOT NULL AND e.signature_image IS NOT NULL) as ready_for_auto_approval
FROM res_users u
LEFT JOIN hr_employee e ON u.employee_id = e.id
WHERE u.active = true AND u.id NOT IN (1, 2);
