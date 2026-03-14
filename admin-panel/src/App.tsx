import { Admin, Resource, Layout, AppBar, UserMenu } from 'react-admin';
import { authProvider } from './authProvider';
import { dataProvider } from './dataProvider';
import PeopleIcon from '@mui/icons-material/People';
import DescriptionIcon from '@mui/icons-material/Description';
import PaymentIcon from '@mui/icons-material/Payment';
import EditNoteIcon from '@mui/icons-material/EditNote';
import ArticleIcon from '@mui/icons-material/Article';

// Import components (we'll create these next)
import { Dashboard } from './components/Dashboard';
import { UserList, UserEdit, UserShow } from './components/users';
import { PromptList, PromptEdit, PromptCreate } from './components/prompts';
import { TransactionList } from './components/transactions';
import { AssignmentList } from './components/assignments';
import { BlogManager } from './components/blogs/BlogManager';

// Custom layout with branding
const MyAppBar = () => (
    <AppBar>
        <span style={{ flex: 1, fontSize: '1.2rem', fontWeight: 'bold' }}>
            Acad3mic-Flow Admin
        </span>
        <UserMenu />
    </AppBar>
);

const MyLayout = (props: any) => <Layout {...props} appBar={MyAppBar} />;

function App() {
    return (
        <Admin
            authProvider={authProvider}
            dataProvider={dataProvider}
            layout={MyLayout}
            dashboard={Dashboard}
            title="Acad3mic-Flow Admin"
        >
            <Resource
                name="users"
                list={UserList}
                edit={UserEdit}
                show={UserShow}
                icon={PeopleIcon}
                options={{ label: 'Users' }}
            />
            <Resource
                name="prompts"
                list={PromptList}
                edit={PromptEdit}
                create={PromptCreate}
                icon={EditNoteIcon}
                options={{ label: 'Humanizer Prompts' }}
            />
            <Resource
                name="transactions"
                list={TransactionList}
                icon={PaymentIcon}
                options={{ label: 'Transactions' }}
            />
            <Resource
                name="assignments"
                list={AssignmentList}
                icon={DescriptionIcon}
                options={{ label: 'Assignments' }}
            />
            <Resource
                name="blog"
                list={BlogManager}
                icon={ArticleIcon}
                options={{ label: 'Blog Automation' }}
            />
        </Admin>
    );
}

export default App;
