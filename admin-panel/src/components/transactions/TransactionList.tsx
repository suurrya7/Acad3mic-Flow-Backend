import {
    List,
    Datagrid,
    TextField,
    DateField,
    NumberField,
    SelectInput,
    FilterButton,
    TopToolbar,
} from 'react-admin';

const TransactionFilters = [
    <SelectInput
        source="status"
        choices={[
            { id: 'success', name: 'Success' },
            { id: 'pending', name: 'Pending' },
            { id: 'failed', name: 'Failed' },
        ]}
    />,
];

const ListActions = () => (
    <TopToolbar>
        <FilterButton />
    </TopToolbar>
);

export const TransactionList = () => (
    <List filters={TransactionFilters} actions={<ListActions />}>
        <Datagrid>
            <TextField source="provider_ref" label="Ref ID" />
            <NumberField source="amount" />
            <NumberField source="words_purchased" />
            <TextField source="status" />
            <DateField source="created_at" showTime />
        </Datagrid>
    </List>
);
