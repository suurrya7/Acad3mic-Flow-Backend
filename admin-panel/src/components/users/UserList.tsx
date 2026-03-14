import {
    List,
    Datagrid,
    TextField,
    EmailField,
    DateField,
    NumberField,
    BooleanField,
    FilterButton,
    TopToolbar,
    SelectColumnsButton,
    TextInput,
    SelectInput,
} from 'react-admin';

const UserFilters = [
    <TextInput label="Search" source="search" alwaysOn />,
    <SelectInput
        source="tier"
        choices={[
            { id: 'Free', name: 'Free' },
            { id: 'Basic', name: 'Basic' },
            { id: 'Standard', name: 'Standard' },
            { id: 'Premium', name: 'Premium' },
            { id: 'Ultimate', name: 'Ultimate' },
        ]}
    />,
];

const ListActions = () => (
    <TopToolbar>
        <FilterButton />
        <SelectColumnsButton />
    </TopToolbar>
);

export const UserList = () => (
    <List filters={UserFilters} actions={<ListActions />}>
        <Datagrid rowClick="show">
            <EmailField source="email" />
            <TextField source="subscription_tier" label="Tier" />
            <NumberField source="word_balance" label="Balance" />
            <BooleanField source="is_admin" label="Admin" />
            <BooleanField source="is_banned" label="Banned" />
            <DateField source="created_at" showTime />
        </Datagrid>
    </List>
);
