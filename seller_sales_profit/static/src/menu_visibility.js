import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { menuService } from "@web/webclient/menus/menu_service";

const dashboardMenu = "seller_sales_profit.menu_seller_sales_profit";

patch(menuService, {
    dependencies: [...menuService.dependencies, "company"],
    async start(env, services) {
        const menus = await super.start(env, services);
        const visible = (menu) =>
            menu.xmlid !== dashboardMenu ||
            services.company.currentCompany.id === session.seller_sales_profit_company_id;
        const getAll = menus.getAll;
        const getMenuAsTree = menus.getMenuAsTree;
        menus.getAll = function () {
            return getAll.call(this).filter(visible);
        };
        menus.getMenuAsTree = function (menuId) {
            const menu = getMenuAsTree.call(this, menuId);
            return { ...menu, childrenTree: menu.childrenTree.filter(visible) };
        };
        return menus;
    },
});
