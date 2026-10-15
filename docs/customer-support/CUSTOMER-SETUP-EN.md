# Northwind Assistant Bot - Admin Setup Guide

This guide explains how to set up the Northwind Assistant bot in your Microsoft 365 organization.

**Estimated time:** 10-15 minutes

---

## Overview

The Northwind Assistant bot uses a **single-tenant deployment model**. This is required by Microsoft - as of July 2025, multi-tenant bot creation is no longer supported.

We are working on publishing to the Microsoft Teams Store, which will simplify future deployments.

**Benefits of single-tenant deployment:**

- The bot runs exclusively in YOUR Azure tenant
- Your data never leaves your organization
- You have full control and visibility over all Azure resources
- You can revoke our access after deployment

---

## Part 1: What You Need to Provide

Before we can deploy the bot, your Azure/Microsoft 365 administrator must provide:

### Required Information

| Information | Description | Example |
|-------------|-------------|---------|
| **Azure Tenant ID** | Your Microsoft 365 organization ID | `12345678-abcd-1234-abcd-1234567890ab` |
| **Azure Subscription ID** | Azure subscription for bot resources | `87654321-dcba-4321-dcba-0987654321ba` |
| **Preferred Azure Region** | Where to host the resources | West Europe, North Europe, etc. |
| **Admin Contact Email** | For deployment coordination | admin@yourcompany.com |

### How to Find Your Tenant ID

Your Tenant ID is the same as your Microsoft 365 Organization ID.

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search for **Microsoft Entra ID** (or "Azure Active Directory")
3. In the Overview page, find **Tenant ID**
4. Copy the GUID value

### How to Find Your Subscription ID

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search for **Subscriptions**
3. Select the subscription you want to use for the bot
4. Copy the **Subscription ID** from the Overview page

---

## Part 2: Granting Deployment Access

We need temporary access to deploy the bot resources.

### Grant Contributor Access

1. Go to Azure Portal → **Subscriptions** → Select your subscription
2. Click **Access control (IAM)** → **Add** → **Add role assignment**
3. Role: **Contributor**
4. Members: Add `guest-admin@example.com` as Guest User
5. Click **Save**

We also need **Application Administrator** role in Microsoft Entra ID to create the bot's app registration. Please grant this role to the same account (`guest-admin@example.com`).

**After deployment:** You can revoke this access. We only need it during initial setup and updates.

---

## Part 3: What You Will See in Azure Portal

After deployment, you will see all resources in your Azure Portal:

```
Resource Groups → rg-northwind-prod
├── bot-northwind-prod-xxxxx     (Bot Service)
├── func-northwind-prod-xxxxx    (Function App)
├── stnorthwindprod-xxxxx        (Storage Account)
└── kv-northwind-prod-xxxxx      (Key Vault)
```

### Setting Up Cost Alerts (Recommended)

1. Azure Portal → **Cost Management** → **Budgets**
2. Click **+ Add**
3. Set monthly budget
4. Add alert at 80% and 100%
5. Email notifications to your admin

### Revoking Access After Deployment

After we complete the deployment:

1. Go to **Subscriptions** → **Access control (IAM)**
2. Find the Guest User account
3. Click **Remove**

For future updates, you can grant temporary access again.

---

## Send Us This Information

Please send the following to your Ragstone contact:

```
Azure Tenant ID:       ___________________________________
Azure Subscription ID: ___________________________________
Preferred Region:      ___________________________________
Admin Contact Email:   ___________________________________
```

Once we receive this, we'll deploy the bot infrastructure and provide you with the Teams app package.

---

## Part 4: Install the App in Teams

After we deploy the infrastructure, you'll receive a `northwind-ai-prod.zip` file customized for your organization.

### Requirements

- Microsoft 365 admin account (Teams Admin or Global Admin)
- Access to Teams Admin Center
- The `northwind-ai-prod.zip` file (provided by us)

### 4.1 Open Teams Admin Center

1. Go to [admin.teams.microsoft.com](https://admin.teams.microsoft.com)
2. Sign in with your admin account

### 4.2 Upload the App

1. In the sidebar, select: **Teams apps** → **Manage apps**
2. Click **+ Upload new app**
3. Select the `northwind-ai-prod.zip` file
4. Wait for validation (10-30 seconds)

### 4.3 Verify the App

After upload, the app should appear in the list with status "Allowed".

---

## Part 5: Configure User Access

The bot should only be accessible to specific employees.

### 5.1 Create a Security Group (optional)

If you don't have a group for bot users yet:

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search for **Microsoft Entra ID** → **Groups**
3. Click **+ New group**
   - Type: **Security**
   - Name: `Northwind Assistant Users`
   - Description: `Employees with access to AI bot`
4. Add members (employees who should use the bot)
5. Click **Create**

### 5.2 Assign Permission Policy

1. In Teams Admin Center, go to: **Teams apps** → **Permission policies**
2. Options:
   - **Option A:** Edit the global policy (all users)
   - **Option B:** Create a new policy for a specific group

#### Option A: Global Policy

1. Click **Global (Org-wide default)**
2. Under **Custom apps**, select **Allow specific apps and block all others**
3. Click **Allow apps** → Search `Northwind Assistant` → **Add**
4. Click **Save**

#### Option B: New Policy for Group

1. Click **+ Add**
2. Name: `Northwind Assistant Access`
3. Under **Custom apps**, allow the Northwind Assistant app
4. Save, then assign the policy to your security group

---

## Part 6: Verify Installation (admin)

1. Open Microsoft Teams → **Apps** → search **Northwind Assistant** → **Add** or **Open**.
2. Send a test message (e.g. `Hello`).
3. Confirm the bot responds within about 5–15 seconds.

Share the end-user guide with employees who get access:

- English: [BOT-USAGE-EN.md](BOT-USAGE-EN.md)
- Polish: [BOT-USAGE-PL.md](BOT-USAGE-PL.md)

---

## What We Deploy in Your Azure Tenant

For transparency, here are the Azure resources we create:

| Resource | Purpose |
|----------|---------|
| **Resource Group** | Container for all resources |
| **Azure Bot Service** | Teams integration |
| **Azure Functions** | Bot backend logic |
| **Storage Account** | Conversation history |
| **Key Vault** | Secure API key storage |
| **App Registration** | Bot identity |

---

## Contact

For any issues, contact us:

- Email: contact@example.com
- Phone: +48 000 000 000

---

*Last updated: January 2026*
